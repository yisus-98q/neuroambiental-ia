"""Scientific Validation Engine (SVE).

Reglas (informe de fortalecimiento científico, §6–§7):
- Los criterios se fijan ANTES de evaluar y quedan congelados (SHA-256 del protocolo, criterios y región).
- Separación geográfica: una evaluación «cv» no puede usar un DEM que toque la región de prueba; una «test»
  debe usar un DEM DENTRO de la región de prueba. La prueba es sellada: una sola evaluación «test» por protocolo.
- Las métricas se leen de la ejecución registrada (no se escriben a mano) y de la variante con el sesgo de
  altura corregido (ausencias en la misma franja de altura).
- Validación condicional = prueba independiente que cumple los criterios + 2 aprobaciones de administradores
  distintos de quien creó el experimento y de quien registró la evaluación; ningún rechazo.
- Datos simulados nunca cumplen criterios.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.models import DataRecord, Run, User
from app.models.validation import Approval, Evaluation, Experiment

MODELS = ("regresion_logistica", "regresion_logistica_base", "regresion_logistica_geo", "bosque_aleatorio")
REFERENCES = ("auc_solo_elevacion_baja", "auc_heuristico_pendiente", "regresion_logistica_base")
VARIANT = "ausencias_mismo_rango_elevacion"
STATES = ("borrador", "evaluado_interno", "evaluado_independiente", "validado_condicional", "retirado")
REQUIRED_APPROVALS = 2


class SVEError(ValueError):
    pass


class NotFound(Exception):
    pass


def _check_bbox(b) -> list[float]:
    if not (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)
            and b[0] < b[2] and b[1] < b[3]):
        raise SVEError("Región de prueba inválida: [minLon, minLat, maxLon, maxLat].")
    return [float(v) for v in b]


def check_criteria(c: dict) -> dict:
    try:
        out = {"auc_min": float(c["auc_min"]), "ic95_inf_min": float(c["ic95_inf_min"]),
               "mejora_min": float(c["mejora_min"]), "referencia": str(c["referencia"])}
    except (KeyError, TypeError, ValueError) as exc:
        raise SVEError("Criterios incompletos: auc_min, ic95_inf_min, mejora_min y referencia.") from exc
    if not (0.5 <= out["auc_min"] <= 1 and 0.5 <= out["ic95_inf_min"] <= 1 and 0 <= out["mejora_min"] <= 0.5):
        raise SVEError("Criterios fuera de rango (AUC entre 0,5 y 1; mejora entre 0 y 0,5).")
    if out["referencia"] not in REFERENCES:
        raise SVEError(f"Referencia desconocida; use una de {REFERENCES}.")
    return out


def protocol_hash(protocol_text: str, criteria: dict, test_region) -> str:
    doc = json.dumps({"protocolo": protocol_text, "criterios": criteria, "region_prueba": test_region},
                     sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(doc.encode("utf-8")).hexdigest()


def create_experiment(db: Session, user: User, *, title: str, module_key: str, question: str, protocol_text: str,
                      criteria: dict, test_region: list | None) -> Experiment:
    crit = check_criteria(criteria)
    region = _check_bbox(test_region) if test_region is not None else None
    exp = Experiment(title=title.strip(), module_key=module_key, question=question.strip(),
                     protocol_text=protocol_text.strip(), criteria=crit, test_region=region,
                     protocol_sha256=protocol_hash(protocol_text.strip(), crit, region), created_by=user.id)
    db.add(exp)
    db.flush()
    audit(db, "sve_crear_experimento", user_id=user.id, target_type="sv_experiment", target_id=exp.id,
          details={"sha256": exp.protocol_sha256}, commit=False)
    db.commit()
    return exp


def get_experiment(db: Session, exp_id: str) -> Experiment:
    exp = db.get(Experiment, exp_id)
    if exp is None:
        raise NotFound("No existe ese experimento.")
    return exp


def _intersects(a: list[float], b: list[float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _inside(a: list[float], b: list[float]) -> bool:
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def extract_metrics(summary: dict, model_ref: str, referencia: str) -> dict:
    """model_ref = «<grupo>/<modelo>» con grupo «todos» o un código de proceso (p. ej. «1000|1500»)."""
    try:
        group, model = model_ref.rsplit("/", 1)
    except ValueError as exc:
        raise SVEError("model_ref debe ser «grupo/modelo», p. ej. «1000|1500/regresion_logistica_geo».") from exc
    if model not in MODELS:
        raise SVEError(f"Modelo desconocido; use uno de {MODELS}.")
    block = summary if group == "todos" else (summary.get("por_proceso") or {}).get(group)
    if not block or VARIANT not in block:
        raise SVEError(f"La ejecución no tiene resultados para el grupo «{group}».")
    v = block[VARIANT]
    esp = (v.get(model) or {}).get("espacial")
    if not esp or esp.get("auc_mean") is None:
        raise SVEError(f"La ejecución no evaluó el modelo «{model}» en el grupo «{group}».")
    ref = ((v.get(referencia) or {}).get("espacial") or {}).get("auc_mean") if referencia in MODELS \
        else v.get(referencia)
    return {"auc": esp["auc_mean"], "auc_sd": esp.get("auc_sd"), "ic95": esp.get("auc_ic95_bloques"),
            "referencia": referencia, "auc_referencia": ref, "n_eventos": v.get("n_presencias"),
            "pr_auc": esp.get("pr_auc"), "brier": esp.get("brier"), "confusion": esp.get("confusion"),
            "variante": VARIANT}


def judge(metrics: dict, crit: dict, simulated: bool) -> tuple[bool, dict]:
    ic = metrics.get("ic95") or [None, None]
    ref = metrics.get("auc_referencia")
    detail = {
        "auc": {"valor": metrics["auc"], "minimo": crit["auc_min"], "cumple": metrics["auc"] >= crit["auc_min"]},
        "ic95_inferior": {"valor": ic[0], "minimo": crit["ic95_inf_min"],
                          "cumple": ic[0] is not None and ic[0] >= crit["ic95_inf_min"]},
        "mejora_sobre_referencia": {"valor": None if ref is None else round(metrics["auc"] - ref, 4),
                                    "minimo": crit["mejora_min"],
                                    "cumple": ref is not None and metrics["auc"] - ref >= crit["mejora_min"]},
        "datos_reales": {"cumple": not simulated},
    }
    return all(d["cumple"] for d in detail.values()), detail


def add_evaluation(db: Session, user: User, exp: Experiment, *, run_id: str, model_ref: str,
                   partition: str) -> Evaluation:
    if exp.status == "retirado":
        raise SVEError("El experimento está retirado.")
    if partition not in ("cv", "test"):
        raise SVEError("Partición inválida: «cv» o «test».")
    run = db.get(Run, run_id)
    if run is None or run.status != "ok" or run.run_type != "validacion_susceptibilidad" \
            or run.module_key != exp.module_key:
        raise SVEError("La ejecución debe ser una validación terminada del mismo módulo que el experimento.")
    dem = db.get(DataRecord, (run.parameters or {}).get("dem_id") or "")
    if dem is None or not dem.bbox:
        raise SVEError("No se encuentra el DEM de esa ejecución para comprobar la separación geográfica.")
    region = exp.test_region
    if partition == "cv" and region and _intersects(dem.bbox, region):
        raise SVEError("Fuga geográfica: el DEM de esta evaluación interna toca la región de prueba.")
    if partition == "test":
        if not region:
            raise SVEError("El experimento no definió una región de prueba independiente.")
        if not _inside(dem.bbox, region):
            raise SVEError("La evaluación de prueba debe usar un DEM dentro de la región de prueba.")
        sealed = db.scalar(select(Evaluation).where(Evaluation.experiment_id == exp.id,
                                                    Evaluation.partition == "test"))
        if sealed is not None:
            raise SVEError("La prueba es sellada: ya existe una evaluación «test» para este protocolo. Para "
                           "volver a probar, cree un experimento nuevo con otra región de prueba.")
    summary = run.result_summary or {}
    metrics = extract_metrics(summary, model_ref, exp.criteria["referencia"])
    met, detail = judge(metrics, exp.criteria, bool(summary.get("simulado")))
    ev = Evaluation(experiment_id=exp.id, partition=partition, run_id=run.id, model_ref=model_ref, metrics=metrics,
                    criteria_met=met, criteria_detail=detail, protocol_sha256=exp.protocol_sha256,
                    created_by=user.id)
    db.add(ev)
    db.flush()
    audit(db, "sve_evaluar", user_id=user.id, target_type="sv_evaluation", target_id=ev.id,
          details={"particion": partition, "cumple": met, "modelo": model_ref}, commit=False)
    db.commit()
    return ev


def approve(db: Session, admin: User, exp: Experiment, *, evaluation_id: str, decision: str,
            comment: str) -> Approval:
    if decision not in ("aprobar", "rechazar"):
        raise SVEError("Decisión inválida: «aprobar» o «rechazar».")
    ev = db.get(Evaluation, evaluation_id)
    if ev is None or ev.experiment_id != exp.id:
        raise NotFound("Esa evaluación no pertenece al experimento.")
    if admin.id in (exp.created_by, ev.created_by):
        raise SVEError("Quien creó el experimento o registró la evaluación no puede aprobarla.")
    if decision == "aprobar":
        if ev.partition != "test":
            raise SVEError("Solo se aprueba una evaluación de prueba independiente («test»).")
        if not ev.criteria_met:
            raise SVEError("La evaluación no cumple los criterios fijados de antemano: no se puede aprobar.")
    if len(comment.strip()) < 20:
        raise SVEError("Justifique la decisión (mín. 20 caracteres).")
    if db.scalar(select(Approval).where(Approval.evaluation_id == ev.id, Approval.reviewer_id == admin.id)):
        raise SVEError("Ya registró una decisión sobre esta evaluación.")
    ap = Approval(experiment_id=exp.id, evaluation_id=ev.id, reviewer_id=admin.id, decision=decision,
                  comment=comment.strip())
    db.add(ap)
    db.flush()
    audit(db, "sve_decision", user_id=admin.id, target_type="sv_evaluation", target_id=ev.id,
          details={"decision": decision}, commit=False)
    db.commit()
    return ap


def retire(db: Session, admin: User, exp: Experiment) -> Experiment:
    exp.status = "retirado"
    audit(db, "sve_retirar", user_id=admin.id, target_type="sv_experiment", target_id=exp.id, commit=False)
    db.commit()
    return exp


def state(db: Session, exp: Experiment) -> str:
    if exp.status == "retirado":
        return "retirado"
    evs = list(db.scalars(select(Evaluation).where(Evaluation.experiment_id == exp.id)))
    tests = [e for e in evs if e.partition == "test"]
    for t in tests:
        aps = list(db.scalars(select(Approval).where(Approval.evaluation_id == t.id)))
        if t.criteria_met and not any(a.decision == "rechazar" for a in aps) and \
                len({a.reviewer_id for a in aps if a.decision == "aprobar"}) >= REQUIRED_APPROVALS:
            return "validado_condicional"
    if tests:
        return "evaluado_independiente"
    return "evaluado_interno" if evs else "borrador"


def to_dict(db: Session, exp: Experiment, detail: bool = False) -> dict:
    out = {"id": exp.id, "title": exp.title, "module_key": exp.module_key, "question": exp.question,
           "criteria": exp.criteria, "test_region": exp.test_region, "protocol_sha256": exp.protocol_sha256,
           "status": exp.status, "estado_cientifico": state(db, exp), "created_at": exp.created_at,
           "created_by": exp.created_by}
    if detail:
        out["protocol_text"] = exp.protocol_text
        out["evaluations"] = [
            {"id": e.id, "partition": e.partition, "run_id": e.run_id, "model_ref": e.model_ref, "metrics": e.metrics,
             "criteria_met": e.criteria_met, "criteria_detail": e.criteria_detail, "created_at": e.created_at,
             "created_by": e.created_by,
             "decisions": [{"reviewer_id": a.reviewer_id, "decision": a.decision, "comment": a.comment,
                            "created_at": a.created_at}
                           for a in db.scalars(select(Approval).where(Approval.evaluation_id == e.id))]}
            for e in db.scalars(select(Evaluation).where(Evaluation.experiment_id == exp.id)
                                .order_by(Evaluation.created_at))]
    return out


def list_experiments(db: Session) -> list[dict]:
    return [to_dict(db, e) for e in db.scalars(select(Experiment).order_by(Experiment.created_at.desc()).limit(100))]
