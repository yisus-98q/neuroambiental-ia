"""Ciclo de vida honesto de un modelo: planificado → entrenado → validado (o retirado)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.core.config import settings
from app.models import AIModel, DataRecord, Prediction, Run, User
from app.models.common import utcnow
from app.modules.neurotraining import trainer
from app.neurodata.service import absolute_path

MIN_EVIDENCE_CHARS = 40
NOT_VALIDATED = ("Modelo NO validado: sus resultados son experimentales y no deben usarse para decisiones "
                 "sin revisión experta.")


class ModelStateError(ValueError):
    pass


def _csv_record(db: Session, record_id: str) -> DataRecord:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "csv" or rec.validation_status != "valido" or not rec.file_path:
        raise ModelStateError("El conjunto de datos debe ser un CSV válido registrado en NEURODATA.")
    return rec


def _artifact_path(model: AIModel) -> tuple[Path, str]:
    rel = Path("models") / model.id / f"v{model.version}.joblib"
    return settings.uploads_dir / rel, rel.as_posix()


def _bump(version: str) -> str:
    try:
        major, minor, patch = (int(x) for x in version.split("."))
    except ValueError:
        return "1.0.0"
    return f"{major + 1}.0.0" if (major, minor, patch) == (0, 0, 0) else f"{major}.{minor + 1}.0"


def train_model(db: Session, user: User, model: AIModel, *, dataset_id: str, task: str, target: str,
                features: list[str], algorithm: str) -> AIModel:
    if model.status not in ("planificado", "entrenado"):
        raise ModelStateError(f"No se puede entrenar un modelo en estado «{model.status}».")
    dataset = _csv_record(db, dataset_id)
    with jobs.exclusive():
        run = Run(run_type="entrenamiento", module_key=model.module_key, model_id=model.id, status="en_proceso",
                  parameters={"dataset": dataset_id, "task": task, "target": target, "features": features,
                              "algorithm": algorithm})
        db.add(run)
        db.commit()
        try:
            ds = trainer.load_dataset(absolute_path(dataset).read_bytes(), target=target, features=features, task=task)
            fitted, metrics = trainer.train(ds, task=task, algorithm=algorithm)
            model.version = _bump(model.version)
            path, rel = _artifact_path(model)
            sha = trainer.save_artifact(fitted, path)
            del fitted
            if ds.classes:
                metrics["classes"] = ds.classes
            model.task, model.target, model.features, model.algorithm = task, target, features, algorithm
            model.dataset_record_id, model.trained_with_simulated = dataset.id, dataset.is_simulated
            model.artifact_path, model.artifact_sha256, model.trained_at = rel, sha, utcnow()
            model.metrics, model.status = metrics, "entrenado"
            model.validation_evidence, model.validated_by = "", None
            run.status, run.finished_at, run.result_summary = "ok", utcnow(), {"version": model.version, **metrics}
            audit(db, "entrenar_modelo", user_id=user.id, target_type="ai_model", target_id=model.id,
                  details={"version": model.version, "simulado": dataset.is_simulated}, commit=False)
            db.commit()
            return model
        except Exception as exc:
            db.rollback()
            run = db.get(Run, run.id)
            run.status, run.finished_at, run.result_summary = "error", utcnow(), {"error": str(exc)[:500]}
            db.commit()
            raise


def validate_model(db: Session, admin: User, model: AIModel, evidence: str) -> AIModel:
    if model.status != "entrenado":
        raise ModelStateError("Solo un modelo «entrenado» puede validarse.")
    if model.trained_with_simulated:
        raise ModelStateError("Un modelo entrenado con datos simulados nunca puede marcarse como validado.")
    if len(evidence.strip()) < MIN_EVIDENCE_CHARS:
        raise ModelStateError(f"Describa la evidencia de validación (mín. {MIN_EVIDENCE_CHARS} caracteres): "
                              "datos independientes usados, métricas obtenidas y quién revisó.")
    model.status, model.validation_evidence, model.validated_by = "validado", evidence.strip(), admin.id
    audit(db, "validar_modelo", user_id=admin.id, target_type="ai_model", target_id=model.id, commit=False)
    db.commit()
    return model


def retire_model(db: Session, admin: User, model: AIModel) -> AIModel:
    model.status = "retirado"
    audit(db, "retirar_modelo", user_id=admin.id, target_type="ai_model", target_id=model.id, commit=False)
    db.commit()
    return model


def predict(db: Session, user: User, model: AIModel, dataset_id: str) -> dict:
    if model.status not in ("entrenado", "validado") or not model.artifact_path or not model.artifact_sha256:
        raise ModelStateError("El modelo debe estar entrenado para predecir.")
    dataset = _csv_record(db, dataset_id)
    fitted = trainer.load_artifact(settings.uploads_dir / model.artifact_path, model.artifact_sha256)
    rows, skipped = trainer.predict_rows(fitted, absolute_path(dataset).read_bytes(), model.features, model.task)
    if model.task == "clasificacion":
        summary = {"counts": dict(Counter(str(r["prediction"]) for r in rows))}
    else:
        vals = [float(r["prediction"]) for r in rows]
        summary = {"mean": round(sum(vals) / len(vals), 4) if vals else None, "n": len(vals)}
    validated = model.status == "validado"
    uncertainty = ("Modelo validado; aun así las predicciones tienen error (ver métricas de prueba)."
                   if validated else NOT_VALIDATED)
    if model.trained_with_simulated:
        uncertainty += " Entrenado con datos SIMULADOS: solo sirve para probar el sistema."
    pred = Prediction(model_id=model.id, target=model.target or "", uncertainty=uncertainty, is_validated=validated,
                      value={"dataset": dataset_id, "n": len(rows), "skipped": skipped, "summary": summary,
                             "sample": rows[:100], "input_simulated": dataset.is_simulated})
    db.add(pred)
    db.flush()
    audit(db, "predecir", user_id=user.id, target_type="prediction", target_id=pred.id, commit=False)
    db.commit()
    return {"prediction_id": pred.id, "model_status": model.status, "n": len(rows), "skipped": skipped,
            "summary": summary, "rows": rows, "uncertainty": uncertainty, "is_validated": validated}
