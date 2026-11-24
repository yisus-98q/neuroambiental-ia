"""NEURODISASTER: importación del inventario real de INGEMMET y validación espacial de la susceptibilidad."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.models import DataRecord, Run, User
from app.models.common import utcnow
from app.modules.disasters import geology, inventory, validation
from app.modules.neuro3d import dem as demlib
from app.neurodata.service import absolute_path, store_file
from app.neurodata.validators import validate_csv
from app.core.config import settings


def rec_res_snapshot(r: dict) -> dict:
    """Recursos medidos hasta ahora (el bloque `resources()` aún no terminó)."""
    import time as _t

    from app.core import hardware
    return {"pico_proceso_mb": round(hardware.process_peak_bytes() / 2**20, 1),
            "perfil": hardware.detect_profile().name, "medido_en": round(_t.time(), 0)}


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


def _ndvi_ring(ndvi_rec: DataRecord, arr, bbox):
    """NDVI en anillo, exigiendo la MISMA malla que el DEM (no se remuestrea en silencio)."""
    import numpy as np

    from app.modules.disasters import terrain_vars
    from app.modules.environmental import raster as envraster
    nd, _ = envraster.read_ndvi(absolute_path(ndvi_rec))   # descala (int16 / 10000) y pone NaN en nodata
    g = (ndvi_rec.extra or {}).get("grid") or {}
    same = nd.shape == arr.shape and g.get("bbox") and all(abs(a - b) < 1e-6 for a, b in zip(g["bbox"], bbox))
    if not same:
        raise validation.ValidationError("El NDVI debe calcularse sobre la misma malla que el DEM (mismo recorte y "
                                         "resolución) para compararlos celda a celda.")
    dxs, dy = demlib._spacing(bbox, arr)
    return terrain_vars.ring_mean(nd, float(np.mean(dxs)), float(dy))


def _record(db: Session, record_id: str, data_type: str) -> DataRecord:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != data_type or not rec.file_path:
        raise NotFound(f"No existe un registro {data_type} con ese id.")
    return rec


def validate(db: Session, user: User | None, *, dem_id: str, inventory_id: str, ratio: int, min_dist_m: float,
             blocks: int, seed: int, n_seeds: int = 5, buffer_m: float = 500.0,
             geology_ids: list[str] | None = None, ndvi_id: str | None = None) -> dict:
    dem_rec = _record(db, dem_id, "raster_dem")
    inv_rec = _record(db, inventory_id, "geojson")
    if not (inv_rec.extra or {}).get("inventory"):
        raise validation.ValidationError("El GeoJSON indicado no es un inventario de eventos importado.")
    params = {"dem_id": dem_id, "inventory_id": inventory_id, "ratio_ausencias": ratio, "distancia_min_m": min_dist_m,
              "bloques": blocks, "semilla": seed, "semillas": n_seeds, "zona_exclusion_m": buffer_m,
              "geologia": list(geology_ids or []), "ndvi_id": ndvi_id}
    ndvi_rec = _record(db, ndvi_id, "raster_ndvi") if ndvi_id else None
    geo_recs = []
    for gid in geology_ids or []:
        g = _record(db, gid, "geojson")
        if not (g.extra or {}).get("geology"):
            raise validation.ValidationError("El GeoJSON indicado no es una capa geológica importada.")
        geo_recs.append(g)
    # Estimación medida: ≈164 MB de pico para 1600x1600 celdas (variables del terreno) + modelos.
    g = (dem_rec.extra or {}).get("grid") or {}
    cells = int(g["width"]) * int(g["height"]) if g else max(int(dem_rec.file_size or 0) // 4, 10_000)
    estimate_mb = 100 + cells * 60 / 1e6 * (1.3 if geology_ids else 1.0)
    with jobs.exclusive("validacion_susceptibilidad", estimate_mb), jobs.resources() as rec_res:
        run = _start(db, "validacion_susceptibilidad", params)
        try:
            arr, bbox = demlib.read_dem(absolute_path(dem_rec))
            fc = validation.load_fc(absolute_path(inv_rec))
            categorical = {}
            for g in geo_recs:
                kind = g.extra["geology"]
                categorical[kind] = geology.rasterize(validation.load_fc(absolute_path(g)), g.extra["field"], arr, bbox)
            extra_layers = {}
            if ndvi_rec is not None:
                extra_layers["ndvi_anillo"] = _ndvi_ring(ndvi_rec, arr, bbox)
            report, X, y, pts = validation.evaluate(arr, bbox, fc, ratio=ratio, min_dist_m=min_dist_m,
                                                    blocks=blocks, seed=seed, n_seeds=n_seeds,
                                                    buffer_m=buffer_m, categorical=categorical,
                                                    extra_layers=extra_layers)
            if ndvi_rec is not None:
                report["ndvi"] = {"id": ndvi_rec.id, "titulo": ndvi_rec.title,
                                  "fecha": ndvi_rec.observed_at.isoformat() if ndvi_rec.observed_at else None,
                                  "escena": (ndvi_rec.extra or {}).get("scene_id"),
                                  "valido_pct": ((ndvi_rec.extra or {}).get("stats") or {}).get("valid_pct")}
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
                           "simulado": simulated, "recursos": {**rec_res_snapshot(rec_res), "estimacion_mb":
                                                               round(estimate_mb)}})
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


def import_geology(db: Session, user: User | None, kind: str, bbox: list[float], fetcher=None) -> DataRecord:
    with jobs.exclusive():
        run = _start(db, "geologia_ingemmet", {"capa": kind, "bbox": bbox})
        try:
            rec = geology.import_layer(db, user, kind, bbox, fetcher=fetcher)
            audit(db, "importar_geologia_ingemmet", user_id=getattr(user, "id", None), target_type="data_record",
                  target_id=rec.id, details={"capa": kind, "bbox": bbox}, commit=False)
            run.status, run.finished_at = "ok", utcnow()
            run.result_summary = {"record_id": rec.id, "capa": kind, "clases": rec.extra.get("classes")}
            db.commit()
            return rec
        except Exception as exc:
            _fail(db, run, exc)
            raise


def list_geology(db: Session) -> list[dict]:
    q = select(DataRecord).where(DataRecord.data_type == "geojson").order_by(DataRecord.received_at.desc()).limit(200)
    return [{"id": r.id, "title": r.title, "capa": r.extra.get("geology"), "campo": r.extra.get("field"),
             "clases": r.extra.get("classes"), "received_at": r.received_at, "license": r.source.license}
            for r in db.scalars(q) if (r.extra or {}).get("geology")]


def external_validation(db: Session, user: User | None, *, dem_a: str, inv_a: str, lito_a: str | None, dem_b: str,
                        inv_b: str, lito_b: str | None, zona_b: str) -> dict:
    """Misión 2.1: entrena SOLO en la zona A y evalúa en la zona B (protocolo prerregistrado)."""
    from app.modules.disasters import external

    recs = {"dem_a": _record(db, dem_a, "raster_dem"), "inv_a": _record(db, inv_a, "geojson"),
            "dem_b": _record(db, dem_b, "raster_dem"), "inv_b": _record(db, inv_b, "geojson")}
    for k in ("inv_a", "inv_b"):
        if not (recs[k].extra or {}).get("inventory"):
            raise validation.ValidationError("Los inventarios deben ser inventarios importados.")
    lito = {k: (_record(db, v, "geojson") if v else None) for k, v in (("a", lito_a), ("b", lito_b))}
    params = {"dem_a": dem_a, "inv_a": inv_a, "lito_a": lito_a, "dem_b": dem_b, "inv_b": inv_b, "lito_b": lito_b,
              "zona_b": zona_b, "protocolo": "docs/MISION_2_1_PROTOCOLO_VALIDACION_EXTERNA.md"}
    def _cells(r):
        g = (r.extra or {}).get("grid") or {}
        return int(g["width"]) * int(g["height"]) if g else max(int(r.file_size or 0) // 4, 10_000)
    # Pico medido: 413 MB con dos mallas de 1600x1600 (≈100 MB base + ≈60 MB por millón de celdas y zona).
    estimate_mb = 100 + (_cells(recs["dem_a"]) + _cells(recs["dem_b"])) * 60 / 1e6
    with jobs.exclusive("validacion_externa", estimate_mb), jobs.resources() as res_:
        run = _start(db, "validacion_externa", params)
        try:
            arr_a, bbox_a = demlib.read_dem(absolute_path(recs["dem_a"]))
            arr_b, bbox_b = demlib.read_dem(absolute_path(recs["dem_b"]))
            out = external.run(arr_a, bbox_a, validation.load_fc(absolute_path(recs["inv_a"])),
                               validation.load_fc(absolute_path(lito["a"])) if lito["a"] else None,
                               arr_b, bbox_b, validation.load_fc(absolute_path(recs["inv_b"])),
                               validation.load_fc(absolute_path(lito["b"])) if lito["b"] else None)
            simulated = any(r.is_simulated for r in list(recs.values()) + [x for x in lito.values() if x])
            out.update({"zona_entrenamiento_bbox": bbox_a, "zona_externa_bbox": bbox_b, "zona_externa": zona_b,
                        "simulado": simulated, "recursos": rec_res_snapshot(res_), "parametros": params})
            audit(db, "validacion_externa", user_id=getattr(user, "id", None), target_type="run", target_id=run.id,
                  details={"zona": zona_b}, commit=False)
            run.status, run.finished_at, run.result_summary = "ok", utcnow(), out
            db.commit()
            return {"run_id": run.id, **out}
        except Exception as exc:
            _fail(db, run, exc)
            raise


def list_external(db: Session) -> list[dict]:
    q = select(Run).where(Run.module_key == "disasters", Run.run_type == "validacion_externa", Run.status == "ok") \
        .order_by(Run.started_at.desc()).limit(20)
    return [{"id": r.id, "fecha": r.finished_at, "zona": (r.result_summary or {}).get("zona_externa"),
             "parametros": r.parameters,
             "estados": {g: v.get("estados") for g, v in ((r.result_summary or {}).get("grupos") or {}).items()},
             "resultado": r.result_summary} for r in db.scalars(q)]
