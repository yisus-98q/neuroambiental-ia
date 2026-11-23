"""Escenarios SIMPLIFICADOS sobre un DEM registrado: susceptibilidad heurística e inundación «bañera».

Todo es SIMULACIÓN demostrativa: no se calibra ni se valida con eventos reales y no predice nada.
Las funciones puras (susceptibility_classes, bathtub, *_metrics) no tocan base de datos ni archivos.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.models import DataRecord, User
from app.models.common import new_id, utcnow
from app.modules.environmental import raster
from app.modules.neuro3d import dem as demlib
from app.modules.neuro3d import service
from app.modules.neuro3d.dem import DemError
from app.neurodata.service import absolute_path, get_or_create_source

KIND_SUSC, KIND_FLOOD = "susceptibilidad", "inundacion_demostrativa"
RUN_SUSC, RUN_FLOOD = "escenario_susceptibilidad", "escenario_inundacion"
BANNER = "SIMULACIÓN — escenario hipotético, no es una predicción"
SUSC_DISCLAIMER = ("Índice heurístico NO calibrado ni validado con inventarios de eventos; "
                   "no predice deslizamientos ni fechas.")
FLOOD_DISCLAIMER = ("Modelo de bañera simplificado (lámina de agua local alrededor del punto, banda ±subida): "
                    "ignora caudal, cauce, rugosidad, tiempo y drenaje, y no representa el flujo aguas abajo; "
                    "no es una simulación hidráulica.")
SLOPE_SATURATION_DEG = 45.0      # pendiente que se considera «máxima» en el índice (función continua lineal)
CLASS_LABELS = {0: "sin dato", 1: "bajo", 2: "medio", 3: "alto"}
RISE_MIN, RISE_MAX = 0.5, 50.0
NDVI_NODATA = raster.NDVI_NODATA
FLOOD_NODATA = -9999.0
SOURCE_NAME = "NEURO 3D LAB: escenarios simplificados (derivados)"


# ---------------------------------------------------------------- utilidades de malla
def row_area_m2(bbox, arr: np.ndarray) -> np.ndarray:
    dx, dy = demlib._spacing(bbox, arr)  # noqa: SLF001 - mismo cálculo que la pendiente
    return dx * dy


def locate(arr: np.ndarray, bbox, lon: float, lat: float) -> tuple[int, int]:
    dlon, dlat = demlib.cell_size(bbox, arr)
    col, row = int(math.floor((lon - bbox[0]) / dlon)), int(math.floor((bbox[3] - lat) / dlat))
    if not (0 <= col < arr.shape[1] and 0 <= row < arr.shape[0]):
        raise DemError("El punto está fuera del DEM cargado.")
    if not np.isfinite(arr[row, col]):
        raise DemError("El punto cae en una celda sin dato de elevación.")
    return row, col


# ---------------------------------------------------------------- susceptibilidad
def check_susceptibility_params(w_slope: float, w_veg: float, t_mid: float, t_high: float) -> None:
    if min(w_slope, w_veg) < 0 or abs(w_slope + w_veg - 1.0) > 1e-6:
        raise DemError("Los pesos w_pendiente y w_vegetacion deben ser >= 0 y sumar 1.")
    if not 0 < t_mid < t_high < 1:
        raise DemError("Los umbrales deben cumplir 0 < umbral_medio < umbral_alto < 1.")


def susceptibility_classes(slope: np.ndarray, ndvi: np.ndarray | None, w_slope: float, w_veg: float,
                           t_mid: float, t_high: float) -> tuple[np.ndarray, np.ndarray]:
    """Índice 0..1 = w_pendiente·pendiente_norm + w_vegetacion·(1 − NDVI_norm). Sin NDVI el índice es solo
    pendiente. Devuelve (índice, clases uint8: 0 sin dato, 1 bajo, 2 medio, 3 alto). Donde falta NDVI → sin dato."""
    check_susceptibility_params(w_slope, w_veg, t_mid, t_high)
    s_norm = np.clip(slope / SLOPE_SATURATION_DEG, 0, 1)
    score = s_norm if ndvi is None else w_slope * s_norm + w_veg * (1 - np.clip(ndvi, 0, 1))
    ok = np.isfinite(score)
    cls = np.zeros(score.shape, dtype="uint8")
    with np.errstate(invalid="ignore"):
        cls[ok] = np.where(score[ok] < t_mid, 1, np.where(score[ok] < t_high, 2, 3))
    return score.astype("float32"), cls


def class_metrics(cls: np.ndarray, bbox) -> dict:
    area = row_area_m2(bbox, cls) / 1e6   # km² por celda, por fila
    total = float((cls > 0).sum(axis=1) @ area)
    out = {"valid_km2": round(total, 3), "classes": []}
    for k in (1, 2, 3):
        km2 = float((cls == k).sum(axis=1) @ area)
        out["classes"].append({"class": k, "label": CLASS_LABELS[k], "km2": round(km2, 3),
                               "pct": round(100 * km2 / total, 2) if total else 0.0})
    return out


def read_ndvi_on_grid(path: Path, bbox, shape: tuple[int, int]) -> np.ndarray:
    """NDVI del registro reproyectado a la malla del DEM (GDAL lee solo lo necesario). NaN sin dato."""
    h, w = shape
    t = rasterio.transform.from_bounds(*bbox, w, h)
    out = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(path) as src:
        reproject(rasterio.band(src, 1), out, dst_transform=t, dst_crs=raster.WGS84,
                  src_nodata=NDVI_NODATA, dst_nodata=float("nan"), resampling=Resampling.average)
    return out / raster.NDVI_SCALE


# ---------------------------------------------------------------- inundación tipo bañera
def check_rise(rise_m: float) -> None:
    if not RISE_MIN <= rise_m <= RISE_MAX:
        raise DemError(f"La subida de nivel debe estar entre {RISE_MIN} y {RISE_MAX} m.")


def bathtub(arr: np.ndarray, bbox, lon: float, lat: float, rise_m: float) -> tuple[np.ndarray, dict]:
    """Lámina de agua LOCAL: celdas conectadas (4-vecindad) al punto cuya elevación está entre
    (elevación del punto − subida) y (elevación del punto + subida).

    Por qué la banda inferior: una «bañera» pura sobre un valle en pendiente inunda todo el valle aguas
    abajo (más bajo que el punto) con profundidades de cientos de metros, lo que es físicamente absurdo
    (el agua escurre). Verificado con el DEM real de Huaraz: sin banda, 2 m de subida daban 42 km² y
    335 m de profundidad. La banda limita el escenario al entorno del punto; no modela el flujo.
    Devuelve (profundidad float32 con 0 en seco y NaN sin dato, métricas)."""
    check_rise(rise_m)
    row, col = locate(arr, bbox, lon, lat)
    base = float(arr[row, col])
    level = base + rise_m
    with np.errstate(invalid="ignore"):
        low = np.isfinite(arr) & (arr <= level) & (arr >= base - rise_m)
    labels, _ = ndimage.label(low)           # estructura por defecto: 4-vecindad
    flooded = labels == labels[row, col]
    depth = np.where(np.isfinite(arr), 0.0, np.nan).astype("float32")
    depth[flooded] = (level - arr[flooded]).astype("float32")
    cell = (row_area_m2(bbox, arr))[:, None]
    area_m2 = float((flooded * cell).sum())
    vol = float((np.where(flooded, depth, 0) * cell).sum())
    touches = bool(flooded[0].any() or flooded[-1].any() or flooded[:, 0].any() or flooded[:, -1].any())
    return depth, {"start_elevation_m": round(level - rise_m, 1), "water_level_m": round(level, 1),
                   "rise_m": rise_m, "flooded_km2": round(area_m2 / 1e6, 4), "volume_m3": round(vol),
                   "max_depth_m": round(float(depth[flooded].max()), 2), "flooded_cells": int(flooded.sum()),
                   "touches_dem_border": touches, "lower_bound_m": round(base - rise_m, 1),
                   "method": "lámina local: banda ±subida alrededor de la cota del punto"}


def observed_state(arr: np.ndarray, bbox) -> dict:
    """Estado actual: datos reales del DEM (sin escenario)."""
    area_km2 = float(np.isfinite(arr).sum(axis=1) @ (row_area_m2(bbox, arr) / 1e6))
    return {"elevation": demlib.elevation_stats(arr), "slope_stats": demlib.slope_stats(demlib.slope_deg(arr, bbox)),
            "area_km2": round(area_km2, 3), "is_simulated": False, "label": "Estado actual (observado)"}


# ---------------------------------------------------------------- archivos
def _profile(grid_bbox, shape, dtype, nodata) -> dict:
    h, w = shape
    return {"driver": "GTiff", "width": w, "height": h, "count": 1, "dtype": dtype, "crs": raster.WGS84,
            "transform": rasterio.transform.from_bounds(*grid_bbox, w, h), "nodata": nodata, "compress": "deflate"}


def _susc_rgba(cls: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*cls.shape, 4), dtype="uint8")
    rgba[cls == 1], rgba[cls == 2], rgba[cls == 3] = (67, 160, 71, 200), (253, 216, 53, 210), (211, 47, 47, 220)
    return rgba


def _flood_rgba(depth: np.ndarray, vmax: float) -> np.ndarray:
    rgba = np.zeros((*depth.shape, 4), dtype="uint8")
    wet = np.isfinite(depth) & (depth > 0)
    t = np.clip(np.nan_to_num(depth) / max(vmax, 1e-6), 0, 1)
    rgba[..., 0] = (150 - 120 * t).astype("uint8")
    rgba[..., 1] = (200 - 120 * t).astype("uint8")
    rgba[..., 2] = 240
    rgba[..., 3] = np.where(wet, 210, 0)
    return rgba


def _load_ndvi_record(db: Session, ndvi_id: str, dem_bbox) -> DataRecord:
    rec = db.get(DataRecord, ndvi_id)
    if rec is None or rec.data_type != "raster_ndvi":
        raise service.NotFound("Registro NDVI no encontrado.")
    if not absolute_path(rec).is_file():
        raise service.NotFound("El archivo NDVI ya no está en el disco.")
    b = rec.bbox or []
    if len(b) != 4 or b[2] <= dem_bbox[0] or b[0] >= dem_bbox[2] or b[3] <= dem_bbox[1] or b[1] >= dem_bbox[3]:
        raise DemError("El NDVI elegido no se superpone al área del DEM.")
    return rec


def _prepare(db: Session, dem_id: str, ndvi_id: str | None):
    rec = service._dem_record(db, dem_id)  # noqa: SLF001
    arr, bbox = demlib.read_dem(absolute_path(rec))
    ndvi_rec, ndvi = None, None
    if ndvi_id:
        ndvi_rec = _load_ndvi_record(db, ndvi_id, bbox)
        ndvi = read_ndvi_on_grid(absolute_path(ndvi_rec), bbox, arr.shape)
        if not np.isfinite(ndvi[np.isfinite(arr)]).any():
            raise DemError("El NDVI elegido no se superpone al área del DEM (sin celdas con dato en común).")
    return rec, arr, bbox, ndvi_rec, ndvi


# ---------------------------------------------------------------- registro de escenarios
def _store(db: Session, user: User, *, run_type: str, kind: str, title: str, dem_rec: DataRecord,
           ndvi_rec: DataRecord | None, array: np.ndarray, dtype: str, nodata, rgba: np.ndarray, params: dict,
           stats: dict, disclaimer: str, unit: str, provenance: str, run) -> DataRecord:
    record_id = new_id()
    now = utcnow()
    rel = Path("scenarios") / f"{now:%Y}" / f"{now:%m}" / f"{record_id}_{kind}.tif"
    tif = settings.uploads_dir / rel
    png = tif.with_suffix(".png")
    try:
        tif.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(tif, "w", **_profile(dem_rec.bbox, array.shape, dtype, nodata)) as dst:
            dst.write(array, 1)
        raster.write_png(png, rgba)
        source = get_or_create_source(db, SOURCE_NAME, "simulacion", "Derivado de datos abiertos con atribución",
                                      service.SOURCE_URL)
        sim = bool(dem_rec.is_simulated or (ndvi_rec.is_simulated if ndvi_rec else False))
        record = DataRecord(
            id=record_id, source_id=source.id, data_type="raster_escenario", title=title, bbox=list(dem_rec.bbox),
            unit=unit, file_format="image/tiff", validation_status="valido", quality="sin_evaluar",
            provenance=provenance, is_simulated=sim, file_path=rel.as_posix(), file_size=tif.stat().st_size,
            sha256=service._sha256(tif),  # noqa: SLF001
            extra={"kind": kind, "scenario": True, "banner": BANNER, "disclaimer": disclaimer, "params": params,
                   "stats": stats, "dem_id": dem_rec.id, "ndvi_id": ndvi_rec.id if ndvi_rec else None,
                   "preview": png.name, "grid": {"width": array.shape[1], "height": array.shape[0]},
                   "validated": False},
            created_by=user.id)
        db.add(record)
        db.flush()
        audit(db, run_type, user_id=user.id, target_type="data_record", target_id=record.id,
              details={"dem": dem_rec.id, "ndvi": ndvi_rec.id if ndvi_rec else None}, commit=False)
        service._finish_run(db, run, "ok", {"record_id": record.id, **stats})  # noqa: SLF001
        return record
    except Exception:
        tif.unlink(missing_ok=True)
        png.unlink(missing_ok=True)
        raise


def run_susceptibility(db: Session, user: User, *, dem_id: str, ndvi_id: str | None, w_slope: float, w_veg: float,
                       t_mid: float, t_high: float) -> DataRecord:
    check_susceptibility_params(w_slope, w_veg, t_mid, t_high)
    with service._exclusive():  # noqa: SLF001
        params = {"dem_id": dem_id, "ndvi_id": ndvi_id, "w_pendiente": w_slope, "w_vegetacion": w_veg,
                  "umbral_medio": t_mid, "umbral_alto": t_high}
        run = service._start_run(db, RUN_SUSC, params)  # noqa: SLF001
        try:
            rec, arr, bbox, ndvi_rec, ndvi = _prepare(db, dem_id, ndvi_id)
            _, cls = susceptibility_classes(demlib.slope_deg(arr, bbox), ndvi, w_slope, w_veg, t_mid, t_high)
            stats = class_metrics(cls, bbox)
            if stats["valid_km2"] == 0:
                raise DemError("No quedaron celdas con dato para calcular el índice.")
            eff = {"w_pendiente": w_slope, "w_vegetacion": w_veg} if ndvi is not None else \
                {"w_pendiente": 1.0, "w_vegetacion": 0.0}
            params["pesos_efectivos"] = eff
            stats["ndvi_used"] = ndvi is not None
            return _store(db, user, run_type=RUN_SUSC, kind=KIND_SUSC, dem_rec=rec, ndvi_rec=ndvi_rec, array=cls,
                          dtype="uint8", nodata=0, rgba=_susc_rgba(cls), params=params, stats=stats,
                          title=f"SIMULACIÓN · Susceptibilidad heurística · {rec.title}", unit="clase (1 bajo, 2 medio, 3 alto)",
                          disclaimer=SUSC_DISCLAIMER, run=run,
                          provenance=(f"{BANNER}. Índice = {eff['w_pendiente']}·pendiente/45° + {eff['w_vegetacion']}·(1−NDVI) "
                                      f"sobre el DEM {rec.id}" + (f" y el NDVI {ndvi_rec.id}" if ndvi_rec else " (sin NDVI)")
                                      + f". Umbrales {t_mid} / {t_high}. {SUSC_DISCLAIMER}"))
        except Exception as exc:
            db.rollback()
            service._finish_run(db, run, "error", {"error": str(exc)[:500]})  # noqa: SLF001
            raise


def run_flood(db: Session, user: User, *, dem_id: str, lon: float, lat: float, rise_m: float) -> DataRecord:
    check_rise(rise_m)
    with service._exclusive():  # noqa: SLF001
        params = {"dem_id": dem_id, "lon": lon, "lat": lat, "rise_m": rise_m}
        run = service._start_run(db, RUN_FLOOD, params)  # noqa: SLF001
        try:
            rec, arr, bbox, _, _ = _prepare(db, dem_id, None)
            depth, stats = bathtub(arr, bbox, lon, lat, rise_m)
            out = np.where(np.isfinite(depth), depth, FLOOD_NODATA).astype("float32")
            return _store(db, user, run_type=RUN_FLOOD, kind=KIND_FLOOD, dem_rec=rec, ndvi_rec=None, array=out,
                          dtype="float32", nodata=FLOOD_NODATA, rgba=_flood_rgba(depth, stats["max_depth_m"]),
                          params=params, stats=stats, disclaimer=FLOOD_DISCLAIMER, unit="m (profundidad hipotética)",
                          title=f"SIMULACIÓN · Inundación demostrativa +{rise_m} m · {rec.title}", run=run,
                          provenance=(f"{BANNER}. Subida de nivel de {rise_m} m desde ({lon}, {lat}) sobre el DEM "
                                      f"{rec.id}. {FLOOD_DISCLAIMER}"))
        except Exception as exc:
            db.rollback()
            service._finish_run(db, run, "error", {"error": str(exc)[:500]})  # noqa: SLF001
            raise


# ---------------------------------------------------------------- comparador (en memoria, sin guardar)
def compare(db: Session, *, dem_id: str, ndvi_id: str | None, configs: list[dict]) -> dict:
    if not 2 <= len(configs) <= 4:
        raise DemError("Se comparan entre 2 y 4 configuraciones.")
    with service._exclusive():  # noqa: SLF001
        rec, arr, bbox, ndvi_rec, ndvi = _prepare(db, dem_id, ndvi_id if any(
            c["kind"] == KIND_SUSC for c in configs) else None)
        slope = demlib.slope_deg(arr, bbox)
        rows = []
        for i, c in enumerate(configs, 1):
            label = c.get("label") or f"Escenario {i}"
            if c["kind"] == KIND_SUSC:
                _, cls = susceptibility_classes(slope, ndvi, c["w_pendiente"], c["w_vegetacion"],
                                                c["umbral_medio"], c["umbral_alto"])
                rows.append({"label": label, "kind": KIND_SUSC, "params": c, "metrics": class_metrics(cls, bbox),
                             "disclaimer": SUSC_DISCLAIMER})
            else:
                _, m = bathtub(arr, bbox, c["lon"], c["lat"], c["rise_m"])
                rows.append({"label": label, "kind": KIND_FLOOD, "params": c, "metrics": m,
                             "disclaimer": FLOOD_DISCLAIMER})
        return {"banner": BANNER, "dem_id": rec.id, "ndvi_id": ndvi_rec.id if ndvi_rec else None,
                "observed": observed_state(arr, bbox), "scenarios": rows, "saved": False}


# ---------------------------------------------------------------- consulta
def list_scenario_records(db: Session, dem_id: str | None = None) -> list[DataRecord]:
    q = select(DataRecord).where(DataRecord.data_type == "raster_escenario").order_by(
        DataRecord.received_at.desc()).limit(100)
    rows = list(db.scalars(q))
    return [r for r in rows if dem_id is None or (r.extra or {}).get("dem_id") == dem_id]


def scenario_grid(db: Session, record_id: str, max_size: int) -> dict:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "raster_escenario" or not absolute_path(rec).is_file():
        raise service.NotFound("Escenario no encontrado.")
    kind = rec.extra["kind"]
    with rasterio.open(absolute_path(rec)) as src:
        shape = demlib.target_shape(src.height, src.width, max_size)   # la misma malla que build_mesh
        data = src.read(1, out_shape=shape, resampling=Resampling.nearest)
    if kind == KIND_SUSC:
        values = data.astype("uint8").ravel().tolist()
        legend = [{"value": k, "label": v} for k, v in CLASS_LABELS.items()]
    else:
        data = np.where(data <= FLOOD_NODATA + 1, -1.0, data)     # -1 = sin dato; 0 = seco
        values = np.round(data, 2).astype("float32").ravel().tolist()
        legend = [{"value": -1, "label": "sin dato"}, {"value": 0, "label": "seco"}]
    return {"id": rec.id, "kind": kind, "width": shape[1], "height": shape[0], "values": values, "legend": legend,
            "max_depth_m": rec.extra["stats"].get("max_depth_m"), "dem_id": rec.extra.get("dem_id"),
            "banner": BANNER, "disclaimer": rec.extra["disclaimer"], "stats": rec.extra["stats"],
            "params": rec.extra["params"]}


def preview_path(db: Session, record_id: str) -> Path:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "raster_escenario":
        raise service.NotFound("Escenario no encontrado.")
    p = absolute_path(rec).with_suffix(".png")
    if not p.is_file():
        raise service.NotFound("Vista previa no disponible.")
    return p
