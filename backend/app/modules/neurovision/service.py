"""Orquestación de NEUROVISION: análisis de una imagen y comparación de dos imágenes de NEURODATA."""
from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.core.config import settings
from app.models import DataRecord, Run, User
from app.models.common import new_id, utcnow
from app.modules.neurovision import processing as proc
from app.neurodata.service import absolute_path, get_or_create_source

SOURCE_NAME = "NEUROVISION (OpenCV)"
SOURCE_LICENSE = "Derivado del registro original; hereda su licencia"

Busy = jobs.Busy
_exclusive = jobs.exclusive
ImageError, ParamError, AlignError = proc.ImageError, proc.ParamError, proc.AlignError


class NotFound(Exception):
    pass


def _start_run(db: Session, run_type: str, params: dict) -> Run:
    # Con el candado tomado, cualquier ejecución «en_proceso» es de un servidor que se detuvo.
    for stale in db.scalars(select(Run).where(Run.module_key == "neurovision", Run.status == "en_proceso")):
        stale.status, stale.finished_at = "error", utcnow()
        stale.result_summary = {"error": "Interrumpido: el servidor se detuvo durante el proceso."}
    run = Run(run_type=run_type, module_key="neurovision", status="en_proceso", parameters=params)
    db.add(run)
    db.commit()
    return run


def _finish_run(db: Session, run: Run, status: str, summary: dict) -> None:
    run.status, run.finished_at, run.result_summary = status, utcnow(), summary
    db.commit()


def _load(db: Session, record_id: str) -> tuple[DataRecord, "proc.np.ndarray"]:
    rec = db.get(DataRecord, record_id)
    if rec is None:
        raise NotFound(f"Registro {record_id} no encontrado.")
    if rec.data_type != "imagen":
        raise ImageError(f"El registro {record_id} no es una imagen (tipo: {rec.data_type}).")
    if rec.validation_status != "valido" or not rec.file_path:
        raise ImageError(f"El registro {record_id} no tiene una imagen válida almacenada.")
    path = absolute_path(rec)
    if not path.is_file():
        raise ImageError(f"El archivo de {record_id} ya no existe en el almacenamiento local.")
    return rec, proc.decode_image(path.read_bytes())


def _save(images: dict[str, "proc.np.ndarray | None"], record_id: str) -> tuple[dict[str, str], list[Path]]:
    now = utcnow()
    rel_dir = Path("vision") / f"{now:%Y}" / f"{now:%m}"
    (settings.uploads_dir / rel_dir).mkdir(parents=True, exist_ok=True)
    rels, written = {}, []
    try:
        for key, img in images.items():
            if img is None:
                continue
            rel = rel_dir / (f"{record_id}.png" if key == "processed" else f"{record_id}_{key}.png")
            dest = settings.uploads_dir / rel
            dest.write_bytes(proc.encode_png(img))
            written.append(dest)
            rels[key] = rel.as_posix()
    except Exception:
        for p in written:  # no dejar PNG huérfanos si falla una escritura intermedia
            p.unlink(missing_ok=True)
        raise
    return rels, written


def _record(db, user, *, record_id, title, source_rec, provenance, rels, written, extra, simulated) -> DataRecord:
    source = get_or_create_source(db, SOURCE_NAME, "procesamiento", SOURCE_LICENSE)
    raw = written[0].read_bytes()
    rec = DataRecord(
        id=record_id, source_id=source.id, data_type="imagen_procesada", title=title,
        latitude=source_rec.latitude, longitude=source_rec.longitude, bbox=source_rec.bbox,
        observed_at=source_rec.observed_at, file_format="image/png", validation_status="valido",
        quality="sin_evaluar", provenance=provenance, is_simulated=simulated, file_path=rels["processed"],
        file_size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        extra={**extra, "overlay": rels.get("overlay"), "original_name": f"{record_id}.png"},
        created_by=user.id,
    )
    db.add(rec)
    db.flush()
    return rec


def _cleanup(paths: list[Path]) -> None:
    for p in paths:
        p.unlink(missing_ok=True)


def analyze(db: Session, user: User, *, record_id: str, operation: str, params: dict | None) -> DataRecord:
    clean = proc.validate_params(operation, params)
    with _exclusive():
        run = _start_run(db, "vision_analisis", {"record_id": record_id, "operation": operation, "params": clean})
        written: list[Path] = []
        try:
            src, img = _load(db, record_id)
            work, info = proc.to_work_size(img)
            del img
            res = proc.run_operation(work, operation, clean)
            new = new_id()
            rels, written = _save({"processed": res["processed"], "overlay": res["overlay"]}, new)
            label = proc.OPERATIONS[operation]["label"]
            rec = _record(
                db, user, record_id=new, title=f"{label}: {src.title}", source_rec=src, rels=rels, written=written,
                simulated=src.is_simulated,
                provenance=(f"Imagen original {src.id} («{src.title}», sha256 {src.sha256}). Operación {operation} "
                            f"con parámetros {clean}, OpenCV {proc.OPENCV_VERSION}. Procesamiento determinístico."),
                extra={"kind": "analisis", "operation": operation, "params": clean,
                       "source_record": src.id, "opencv_version": proc.OPENCV_VERSION, "work_size": info,
                       "features": res["features"], "regions": res["regions"],
                       "regions_total": res["regions_total"], "regions_truncated": res["regions_truncated"],
                       "confidence": None, "confidence_note": proc.CONFIDENCE_NOTE,
                       "limitations": res["limitations"], "run_id": run.id})
            audit(db, "vision_analisis", user_id=user.id, target_type="data_record", target_id=rec.id,
                  details={"operacion": operation, "origen": src.id}, commit=False)
            _finish_run(db, run, "ok", {"record_id": rec.id, "operation": operation,
                                        "regions_total": res["regions_total"]})
            return rec
        except Exception as exc:
            db.rollback()
            _cleanup(written)
            _finish_run(db, run, "error", {"error": str(exc)[:500]})
            raise


def compare(db: Session, user: User, *, record_a: str, record_b: str) -> DataRecord:
    if record_a == record_b:
        raise ImageError("Seleccione dos imágenes distintas.")
    with _exclusive():
        run = _start_run(db, "vision_analisis", {"operation": "comparacion", "record_a": record_a,
                                                 "record_b": record_b})
        written: list[Path] = []
        try:
            ra, ia = _load(db, record_a)
            wa, info_a = proc.to_work_size(ia)
            del ia
            rb, ib = _load(db, record_b)
            wb, info_b = proc.to_work_size(ib)
            del ib
            res = proc.compare_images(wa, wb)
            new = new_id()
            rels, written = _save({"processed": res["processed"]}, new)
            rec = _record(
                db, user, record_id=new, title=f"Cambios: {ra.title} → {rb.title}", source_rec=ra, rels=rels,
                written=written, simulated=ra.is_simulated or rb.is_simulated,
                provenance=(f"Comparación de {ra.id} (sha256 {ra.sha256}) y {rb.id} (sha256 {rb.sha256}): "
                            f"alineación ORB + homografía RANSAC, diferencia en gris con histogramas igualados, "
                            f"umbral Otsu y limpieza morfológica. OpenCV {proc.OPENCV_VERSION}."),
                extra={"kind": "comparacion", "operation": "comparacion", "params": {},
                       "record_a": ra.id, "record_b": rb.id, "source_record": ra.id,
                       "opencv_version": proc.OPENCV_VERSION, "work_size": {"a": info_a, "b": info_b},
                       "features": res["features"], "regions": res["regions"],
                       "regions_total": res["regions_total"], "regions_truncated": res["regions_truncated"],
                       "alignment": res["align"], "confidence": None, "confidence_note": proc.CONFIDENCE_NOTE,
                       "limitations": res["limitations"], "run_id": run.id})
            audit(db, "vision_comparacion", user_id=user.id, target_type="data_record", target_id=rec.id,
                  details={"a": ra.id, "b": rb.id}, commit=False)
            _finish_run(db, run, "ok", {"record_id": rec.id, "cambio_pct": res["features"]["cambio_pct"]})
            return rec
        except Exception as exc:
            db.rollback()
            _cleanup(written)
            _finish_run(db, run, "error", {"error": str(exc)[:500]})
            raise


def overlay_path(rec: DataRecord) -> Path:
    rel = (rec.extra or {}).get("overlay")
    if not rel:
        raise FileNotFoundError("Este resultado no tiene superposición.")
    path = (settings.uploads_dir / rel).resolve()
    if settings.uploads_dir.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError("Superposición no disponible.")
    return path
