"""NEURODISASTER: importación del inventario real de INGEMMET y validación espacial de la susceptibilidad."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.models import DataRecord, Run, User
from app.models.common import utcnow
from app.modules.disasters import inventory, validation
from app.modules.neuro3d import dem as demlib
from app.neurodata.service import absolute_path, store_file
from app.neurodata.validators import validate_csv
from app.core.config import settings


class NotFound(Exception):
    pass


def _start(db: Session, run_type: str, params: dict) -> Run:
    for stale in db.scalars(select(Run).where(Run.module_key == "disasters", Run.status == "en_proceso")):
        stale.status, stale.finished_at = "error", utcnow()
        stale.result_summary = {"error": "Interrumpido: el servidor se detuvo durante el proceso."}
    run = Run(run_type=run_type, module_key="disasters", status="en_proceso", parameters=params)
    db.add(run)
    db.commit()
    return run


def _fail(db: Session, run: Run, exc: Exception) -> None:
    db.rollback()
    run = db.get(Run, run.id)
    run.status, run.finished_at, run.result_summary = "error", utcnow(), {"error": str(exc)[:500]}
    db.commit()


def import_inventory(db: Session, user: User | None, bbox: list[float], fetcher=None) -> DataRecord:
    with jobs.exclusive():
        run = _start(db, "inventario_ingemmet", {"bbox": bbox})
        try:
            rec = inventory.import_events(db, user, bbox, fetcher=fetcher or inventory.fetch_events)
            audit(db, "importar_inventario_ingemmet", user_id=getattr(user, "id", None), target_type="data_record", target_id=rec.id,
                  details={"eventos": rec.extra.get("features"), "bbox": bbox}, commit=False)
            run.status, run.finished_at = "ok", utcnow()
            run.result_summary = {"record_id": rec.id, "eventos": rec.extra.get("features"),
                                  "tipos": rec.extra.get("tipos_peligro")}
            db.commit()
            return rec
        except Exception as exc:
            _fail(db, run, exc)
            raise


def _record(db: Session, record_id: str, data_type: str) -> DataRecord:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != data_type or not rec.file_path:
        raise NotFound(f"No existe un registro {data_type} con ese id.")
    return rec


def validate(db: Session, user: User | None, *, dem_id: str, inventory_id: str, ratio: int, min_dist_m: float,
             blocks: int, seed: int, n_seeds: int = 5, buffer_m: float = 500.0) -> dict:
    dem_rec = _record(db, dem_id, "raster_dem")
    inv_rec = _record(db, inventory_id, "geojson")
    if not (inv_rec.extra or {}).get("inventory"):
        raise validation.ValidationError("El GeoJSON indicado no es un inventario de eventos importado.")
    params = {"dem_id": dem_id, "inventory_id": inventory_id, "ratio_ausencias": ratio, "distancia_min_m": min_dist_m,
              "bloques": blocks, "semilla": seed, "semillas": n_seeds, "zona_exclusion_m": buffer_m}
    with jobs.exclusive():
        run = _start(db, "validacion_susceptibilidad", params)
        try:
            arr, bbox = demlib.read_dem(absolute_path(dem_rec))
            fc = validation.load_fc(absolute_path(inv_rec))
            report, X, y, pts = validation.evaluate(arr, bbox, fc, ratio=ratio, min_dist_m=min_dist_m,
                                                    blocks=blocks, seed=seed, n_seeds=n_seeds,
                                                    buffer_m=buffer_m)
            raw = validation.dataset_csv(X, y, pts, bbox, arr, report["variables"])
            aj = report["ausencias_mismo_rango_elevacion"]
            simulated = bool(dem_rec.is_simulated or inv_rec.is_simulated)
            ds = store_file(db, raw=raw, extension=".csv", original_name="susceptibilidad_entrenamiento.csv",
                            result=validate_csv(raw, settings.max_csv_rows), source_name=inv_rec.source.name,
                            source_license=inv_rec.source.license,
                            title=f"Dataset susceptibilidad · {aj['n_presencias']} eventos / "
                                  f"{aj['n_ausencias']} pseudo-ausencias (rango de elevación corregido)",
                            observed_at=None, is_simulated=simulated,
                            provenance=(f"Presencias: inventario {inv_rec.id}; pseudo-ausencias aleatorias a ≥ "
                                        f"{min_dist_m} m de eventos y dentro del rango de elevación {aj['rango_elevacion_m']} m "
                                        f"de los eventos (semilla {seed}); variables del DEM {dem_rec.id}. "
                                        "Columna objetivo: evento (1/0)."),
                            user_id=getattr(user, "id", None))
            report.update({"dataset_record_id": ds.id, "dem_id": dem_id, "inventory_id": inventory_id,
                           "simulado": simulated})
            audit(db, "validar_susceptibilidad", user_id=getattr(user, "id", None), target_type="run", target_id=run.id,
                  details={"auc_heuristico": report["ausencias_libres"]["auc_heuristico_pendiente"]}, commit=False)
            run.status, run.finished_at, run.result_summary = "ok", utcnow(), report
            db.commit()
            return {"run_id": run.id, **report}
        except Exception as exc:
            _fail(db, run, exc)
            raise


def list_runs(db: Session) -> list[dict]:
    q = select(Run).where(Run.module_key == "disasters").order_by(Run.started_at.desc()).limit(50)
    return [{"id": r.id, "run_type": r.run_type, "status": r.status, "started_at": r.started_at,
             "finished_at": r.finished_at, "parameters": r.parameters, "result_summary": r.result_summary}
            for r in db.scalars(q)]


def list_inventories(db: Session) -> list[dict]:
    q = select(DataRecord).where(DataRecord.data_type == "geojson").order_by(DataRecord.received_at.desc()).limit(200)
    return [{"id": r.id, "title": r.title, "bbox": r.bbox, "received_at": r.received_at,
             "is_simulated": r.is_simulated, "source": r.source.name, "license": r.source.license,
             "eventos": (r.extra or {}).get("features"), "tipos_peligro": (r.extra or {}).get("tipos_peligro")}
            for r in db.scalars(q) if (r.extra or {}).get("inventory")]
