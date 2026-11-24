"""Orquestación de NEURO 3D LAB: DEM real (Copernicus GLO-30), malla para el visor y escenario demostrativo."""
from __future__ import annotations

import contextlib
import hashlib
import math
from pathlib import Path

import numpy as np
import rasterio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.core.config import settings
from app.models import DataRecord, Run, User
from app.models.common import new_id, utcnow
from app.modules.environmental import raster, remote
from app.modules.neuro3d import dem as demlib
from app.modules.neuro3d.dem import DemError
from app.neurodata.service import absolute_path, get_or_create_source

SOURCE_NAME = "Copernicus DEM GLO-30 (AWS Open Data)"
SOURCE_LICENSE = "Copernicus DEM: uso libre con atribución"
SOURCE_URL = "https://registry.opendata.aws/copernicus-dem/"
ATTRIBUTION = ("Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, "
               "proporcionado bajo COPERNICUS por la Unión Europea y la ESA")
BASE_URL = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"
SCENARIO_RUN_TYPE = "escenario_trayectoria"
SCENARIO_UNCERTAINTY = ("La trayectoria depende de la resolución del DEM (≈100 m por defecto), ignora cauces, "
                        "vegetación, suelo, agua y obstáculos, y los errores verticales del DEM (varios metros) "
                        "pueden desviar el camino. No indica probabilidad ni alcance real de ningún evento.")

HEAVY_RUNS = ("dem", "escenario_susceptibilidad", "escenario_inundacion")
Busy = jobs.Busy
_exclusive = jobs.exclusive


class ProcessingError(Exception):
    pass


class NotFound(LookupError):
    pass


class TileMissing(Exception):
    """La tesela no existe (p. ej. océano abierto: GLO-30 no publica teselas sin tierra)."""


class RemoteDemBackend:
    """Acceso remoto abstraído: se sustituye en las pruebas por teselas locales."""

    def tile_href(self, tile: demlib.Tile) -> str:
        return f"{BASE_URL}/{tile.name}/{tile.name}.tif"

    @contextlib.contextmanager
    def open_band(self, href: str, opener: remote.HttpsOpener):
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
                src = rasterio.open(href, opener=opener)
        except Exception as exc:
            if "404" in str(exc):
                raise TileMissing(href) from exc
            raise
        with src:
            yield src


backend = RemoteDemBackend()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _start_run(db: Session, run_type: str, params: dict) -> Run:
    for stale in db.scalars(select(Run).where(Run.module_key == "neuro3d", Run.run_type.in_(HEAVY_RUNS),
                                              Run.status == "en_proceso")):
        stale.status, stale.finished_at = "error", utcnow()
        stale.result_summary = {"error": "Interrumpido: el servidor se detuvo durante el proceso."}
    run = Run(run_type=run_type, module_key="neuro3d", status="en_proceso", parameters=params)
    db.add(run)
    db.commit()
    return run


def _finish_run(db: Session, run: Run, status: str, summary: dict) -> None:
    run.status, run.finished_at, run.result_summary = status, utcnow(), summary
    db.commit()


def fetch_dem(db: Session, user: User | None, *, bbox: list[float], res: float, analysis: bool = False) -> DataRecord:
    grid = demlib.make_dem_grid(bbox, res, analysis)  # valida antes de tocar la red
    tiles = demlib.tiles_for_bbox(grid.bbox)
    with _exclusive("dem", 60 + grid.width * grid.height * 4 * 6 / 1e6):
        run = _start_run(db, "dem", {"bbox": list(grid.bbox), "res": res, "tiles": [t.name for t in tiles]})
        tif: Path | None = None
        try:
            opener = remote.HttpsOpener()
            parts, used = [], []
            for tile in tiles:
                try:
                    with backend.open_band(backend.tile_href(tile), opener) as src:
                        part = demlib.read_tile(src, grid)
                except TileMissing:
                    continue  # tesela inexistente (océano): se rellena con las demás
                if np.isfinite(part).any():
                    parts.append(part)
                    used.append(tile.name)
            if not parts:
                raise ProcessingError("Ninguna tesela GLO-30 cubre el área (¿océano abierto?).")
            dem = demlib.mosaic(parts)
            del parts
            stats = demlib.elevation_stats(dem)
            record_id = new_id()
            now = utcnow()
            rel = Path("terrain") / f"{now:%Y}" / f"{now:%m}" / f"{record_id}_dem.tif"
            tif = settings.uploads_dir / rel
            demlib.write_dem(tif, dem, grid)
            slopes = demlib.slope_stats(demlib.slope_deg(dem, grid.bbox))
            source = get_or_create_source(db, SOURCE_NAME, "satelite", SOURCE_LICENSE, SOURCE_URL)
            record = DataRecord(
                id=record_id, source_id=source.id, data_type="raster_dem",
                title=f"DEM GLO-30 [{grid.bbox[0]:.3f}, {grid.bbox[1]:.3f}, {grid.bbox[2]:.3f}, {grid.bbox[3]:.3f}]",
                bbox=list(grid.bbox), unit="m (elevación)", file_format="image/tiff", validation_status="valido",
                quality="media",
                provenance=(f"Teselas {', '.join(used)} leídas por rangos HTTP y remuestreadas (promedio) a una "
                            f"malla EPSG:4326 de {grid.res}° ({grid.width}x{grid.height} px). {ATTRIBUTION}."),
                is_simulated=False, file_path=rel.as_posix(), file_size=tif.stat().st_size, sha256=_sha256(tif),
                extra={"kind": "dem", "analysis": analysis, "elevation": stats, "slope_stats": slopes, "tiles": used,
                       "grid": {"bbox": list(grid.bbox), "res": grid.res, "width": grid.width,
                                "height": grid.height},
                       "download": dict(opener.stats), "attribution": ATTRIBUTION},
                created_by=getattr(user, "id", None),
            )
            db.add(record)
            db.flush()
            audit(db, "dem_glo30", user_id=getattr(user, "id", None), target_type="data_record", target_id=record.id,
                  details={"teselas": used, "bytes": opener.stats.get("bytes", 0)}, commit=False)
            _finish_run(db, run, "ok", {"record_id": record.id, **stats, "download": dict(opener.stats)})
            return record
        except Exception as exc:
            db.rollback()
            if tif is not None:
                tif.unlink(missing_ok=True)  # no dejar archivos huérfanos sin registro
            _finish_run(db, run, "error", {"error": str(exc)[:500]})
            raise


def _dem_record(db: Session, record_id: str) -> DataRecord:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "raster_dem":
        raise NotFound("Terreno no encontrado.")
    if not absolute_path(rec).is_file():
        raise NotFound("El archivo del terreno ya no está en el disco.")
    return rec


def list_terrains(db: Session) -> list[DataRecord]:
    q = select(DataRecord).where(DataRecord.data_type == "raster_dem").order_by(DataRecord.received_at.desc()).limit(50)
    return list(db.scalars(q))


def build_mesh(db: Session, record_id: str, max_size: int) -> dict:
    rec = _dem_record(db, record_id)
    arr, bbox = demlib.read_dem(absolute_path(rec), max_size=max_size)
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        raise ProcessingError("El DEM no tiene datos válidos.")
    lo, hi = float(valid.min()), float(valid.max())
    finite = np.isfinite(arr)
    heights = np.where(finite, arr, lo).round().astype("int16")
    slope = demlib.slope_deg(arr, bbox)
    slopes = np.where(np.isfinite(slope), slope, 0).round().clip(0, 90).astype("uint8")
    h, w = arr.shape
    # Máscara de validez: las celdas sin dato NO deben pintarse como terreno real (el visor las dibuja en gris).
    valid_mask = finite.astype("uint8")
    mid = (bbox[1] + bbox[3]) / 2
    extent = [round((bbox[2] - bbox[0]) * demlib.M_PER_DEG_LON * math.cos(math.radians(mid)), 1),
              round((bbox[3] - bbox[1]) * demlib.M_PER_DEG_LAT, 1)]
    return {"id": rec.id, "width": w, "height": h, "bbox": list(bbox), "min": round(lo), "max": round(hi),
            "heights": heights.ravel().tolist(), "slopes": slopes.ravel().tolist(), "extent_m": extent,
            "valid": valid_mask.ravel().tolist(), "valid_pct": round(100 * float(finite.mean()), 2),
            "slope_stats": rec.extra.get("slope_stats", {}), "attribution": ATTRIBUTION}


def run_flow_path(db: Session, user: User, record_id: str, lon: float, lat: float) -> dict:
    rec = _dem_record(db, record_id)
    arr, bbox = demlib.read_dem(absolute_path(rec))
    result = demlib.flow_path(arr, bbox, lon, lat)
    out = {**result, "disclaimer": demlib.FLOW_DISCLAIMER, "uncertainty": SCENARIO_UNCERTAINTY,
           "is_simulated": True, "record_id": rec.id, "start": {"lon": lon, "lat": lat},
           "dem_resolution_deg": rec.extra.get("grid", {}).get("res")}
    run = Run(run_type=SCENARIO_RUN_TYPE, module_key="neuro3d", status="ok", finished_at=utcnow(),
              parameters={"record_id": rec.id, "lon": lon, "lat": lat, "metodo": "D8", "max_pasos": demlib.MAX_PATH_STEPS},
              result_summary=out)
    db.add(run)
    db.flush()
    audit(db, "escenario_trayectoria", user_id=user.id, target_type="run", target_id=run.id,
          details={"dem": rec.id, "lon": lon, "lat": lat}, commit=False)
    db.commit()
    return {"id": run.id, **out}


def list_scenarios(db: Session, *, with_path: bool = False, limit: int = 50) -> list[dict]:
    q = (select(Run).where(Run.module_key == "neuro3d", Run.run_type == SCENARIO_RUN_TYPE)
         .order_by(Run.started_at.desc()).limit(limit))
    rows = []
    for r in db.scalars(q):
        res = dict(r.result_summary or {})
        if not with_path:
            res.pop("path", None)
        rows.append({"id": r.id, "started_at": r.started_at, "parameters": r.parameters, **res})
    return rows


def get_scenario(db: Session, run_id: str) -> dict:
    run = db.get(Run, run_id)
    if run is None or run.run_type != SCENARIO_RUN_TYPE:
        raise NotFound("Escenario no encontrado.")
    return {"id": run.id, "started_at": run.started_at, "parameters": run.parameters, **(run.result_summary or {})}
