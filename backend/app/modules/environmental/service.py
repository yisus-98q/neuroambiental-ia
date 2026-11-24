"""Orquestación del módulo ambiental: NDVI de una escena y detección de cambios entre dos fechas."""
from __future__ import annotations

import contextlib
import hashlib
from datetime import datetime
from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.core.config import settings
from app.models import DataRecord, Run, User
from app.models.common import new_id, utcnow
from app.modules.environmental import raster, remote
from app.neurodata.service import absolute_path, get_or_create_source

SOURCE_NAME = "Copernicus Sentinel-2 L2A (Earth Search / AWS Open Data)"
SOURCE_LICENSE = "Copernicus: uso libre con atribución"
SOURCE_URL = "https://registry.opendata.aws/sentinel-2-l2a-cogs/"
NDVI_UNCERTAINTY = ("El NDVI es un índice, no una medición de biomasa. Nubes residuales, sombras de relieve, "
                    "nieve, época del año y ángulo solar pueden alterar los valores. Requiere validación.")
CHANGE_UNCERTAINTY = ("Un cambio de NDVI NO confirma deforestación ni daño ambiental: también lo producen "
                      "estacionalidad, cultivos, nieve, nubes no detectadas o diferencias de iluminación. "
                      "Debe validarse con imágenes de alta resolución o trabajo de campo.")

_LOCK = jobs.LOCK
Busy = jobs.Busy
_exclusive = jobs.exclusive


class ProcessingError(Exception):
    pass


class RemoteBackend:
    """Separado para poder sustituirlo en las pruebas por archivos locales."""

    def get_scene(self, item_id: str) -> remote.Scene:
        return remote.get_scene(item_id)

    @contextlib.contextmanager
    def open_band(self, href: str, opener: remote.HttpsOpener):
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open(href, opener=opener) as src:
                yield src


backend = RemoteBackend()


def _paths(record_id: str, suffix: str) -> tuple[Path, Path, str]:
    now = utcnow()
    rel = Path("rasters") / f"{now:%Y}" / f"{now:%m}" / f"{record_id}_{suffix}.tif"
    tif = settings.uploads_dir / rel
    return tif, tif.with_suffix(".png"), rel.as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _band_scale(asset: dict) -> tuple[float, float]:
    bands = asset.get("raster:bands") or [{}]
    return float(bands[0].get("scale", 1.0)), float(bands[0].get("offset", 0.0))


def _start_run(db: Session, run_type: str, params: dict) -> Run:
    # Se llama con el candado tomado: cualquier ejecución «en_proceso» es de un servidor que se detuvo.
    for stale in db.scalars(select(Run).where(Run.module_key == "environmental", Run.status == "en_proceso")):
        stale.status, stale.finished_at = "error", utcnow()
        stale.result_summary = {"error": "Interrumpido: el servidor se detuvo durante el proceso."}
    run = Run(run_type=run_type, module_key="environmental", status="en_proceso", parameters=params)
    db.add(run)
    db.commit()
    return run


def _finish_run(db: Session, run: Run, status: str, summary: dict) -> None:
    run.status, run.finished_at, run.result_summary = status, utcnow(), summary
    db.commit()


def compute_ndvi(db: Session, user: User | None, *, item_id: str, bbox: list[float], res: float) -> DataRecord:
    grid = raster.make_grid(bbox, res)  # valida el área antes de tocar la red
    with _exclusive():
        run = _start_run(db, "ndvi", {"item_id": item_id, "bbox": list(grid.bbox), "res": res})
        try:
            scene = backend.get_scene(item_id)
            missing = [k for k in ("red", "nir", "scl") if k not in scene.assets]
            if missing:
                raise ProcessingError(f"La escena no tiene las bandas necesarias: {missing}")
            opener = remote.HttpsOpener()
            bands = {}
            declared = {}
            for key, resampling in (("red", Resampling.average), ("nir", Resampling.average), ("scl", Resampling.mode)):
                scale, offset = _band_scale(scene.assets[key]) if key != "scl" else (1.0, 0.0)
                declared[key] = offset
                with backend.open_band(scene.assets[key]["href"], opener) as src:
                    # Se lee solo con escala; el desplazamiento se decide después con los datos.
                    bands[key] = raster.read_to_grid(src, grid, resampling=resampling, scale=scale)
            offset, offset_info = raster.choose_offset(bands["red"], bands["scl"], declared["red"])
            if offset:
                bands["red"] += offset
                bands["nir"] += offset
            ndvi, stats = raster.compute_ndvi(bands["red"], bands["nir"], bands["scl"])
            stats["radiometric_offset"] = offset_info
            del bands
            if stats["pixels_valid"] == 0:
                raise ProcessingError("No quedaron píxeles válidos (nubes, sombras o la escena no cubre el área).")
            record_id = new_id()
            tif, png, rel = _paths(record_id, "ndvi")
            raster.write_ndvi(tif, ndvi, grid)
            raster.write_png(png, raster.ndvi_rgba(ndvi))
            del ndvi
            observed = datetime.fromisoformat(scene.datetime.replace("Z", "+00:00")) if scene.datetime else None
            year = observed.year if observed else ""
            source = get_or_create_source(db, SOURCE_NAME, "satelite", SOURCE_LICENSE, SOURCE_URL)
            record = DataRecord(
                id=record_id, source_id=source.id, data_type="raster_ndvi",
                title=f"NDVI {scene.datetime[:10]} · {scene.mgrs_tile}", bbox=list(grid.bbox), observed_at=observed,
                unit="NDVI (-1 a 1)", file_format="image/tiff", validation_status="valido", quality="media",
                provenance=(f"Escena {scene.id} ({scene.platform}, nubosidad {scene.cloud_cover:.1f} %). "
                            f"Bandas B04/B08 y máscara SCL leídas por recorte y reproyectadas a EPSG:4326 "
                            f"con resolución {res}°. Desplazamiento radiométrico aplicado: "
                            f"{offset_info['applied_offset']} ({offset_info['reason']}). "
                            f"Contiene datos modificados de Copernicus Sentinel {year}."),
                is_simulated=False, file_path=rel, file_size=tif.stat().st_size, sha256=_sha256(tif),
                extra={"kind": "ndvi", "scene_id": scene.id, "mgrs_tile": scene.mgrs_tile,
                       "cloud_cover": scene.cloud_cover, "grid": {"bbox": list(grid.bbox), "res": res,
                       "width": grid.width, "height": grid.height}, "stats": stats,
                       "download": dict(opener.stats), "preview": png.name, "uncertainty": NDVI_UNCERTAINTY},
                created_by=getattr(user, "id", None),
            )
            db.add(record)
            db.flush()
            audit(db, "ndvi_sentinel2", user_id=getattr(user, "id", None), target_type="data_record", target_id=record.id,
                  details={"escena": scene.id, "bytes": opener.stats.get("bytes", 0)}, commit=False)
            _finish_run(db, run, "ok", {"record_id": record.id, **stats, "download": dict(opener.stats)})
            return record
        except Exception as exc:
            db.rollback()
            _finish_run(db, run, "error", {"error": str(exc)[:500]})
            raise


def _load_ndvi(db: Session, record_id: str):
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "raster_ndvi":
        raise ProcessingError(f"{record_id} no es un registro NDVI.")
    arr, grid = raster.read_ndvi(absolute_path(rec))
    return rec, arr, grid


def compute_change(db: Session, user: User, *, before_id: str, after_id: str, threshold: float) -> DataRecord:
    if before_id == after_id:
        raise ProcessingError("Seleccione dos NDVI distintos.")
    with _exclusive():
        run = _start_run(db, "deteccion_cambios", {"before": before_id, "after": after_id, "threshold": threshold})
        try:
            rb, before, gb = _load_ndvi(db, before_id)
            ra, after, ga = _load_ndvi(db, after_id)
            if (gb.width, gb.height) != (ga.width, ga.height) or any(
                    abs(x - y) > 1e-9 for x, y in zip(gb.bbox, ga.bbox)) or abs(gb.res - ga.res) > 1e-12:
                raise ProcessingError("Los dos NDVI deben calcularse con la misma área y resolución.")
            if rb.observed_at and ra.observed_at and rb.observed_at > ra.observed_at:
                rb, ra, before, after = ra, rb, after, before  # siempre «antes» → «después»
            classes, stats = raster.detect_change(before, after, gb, threshold)
            del before, after
            record_id = new_id()
            tif, png, rel = _paths(record_id, "cambio")
            raster.write_classes(tif, classes, gb)
            raster.write_png(png, raster.change_rgba(classes))
            del classes
            d1 = rb.observed_at.date().isoformat() if rb.observed_at else "?"
            d2 = ra.observed_at.date().isoformat() if ra.observed_at else "?"
            record = DataRecord(
                id=record_id, source_id=ra.source_id, data_type="raster_cambio",
                title=f"Cambio de NDVI {d1} → {d2}", bbox=list(gb.bbox), observed_at=ra.observed_at,
                unit="clase (1 disminución, 2 aumento)", file_format="image/tiff", validation_status="valido",
                quality="sin_evaluar",
                provenance=(f"Diferencia entre los NDVI {rb.id} y {ra.id} con umbral ±{threshold}. "
                            f"Contiene datos modificados de Copernicus Sentinel "
                            f"{'/'.join(sorted({str(r.observed_at.year) for r in (rb, ra) if r.observed_at}))}."),
                is_simulated=rb.is_simulated or ra.is_simulated, file_path=rel, file_size=tif.stat().st_size,
                sha256=_sha256(tif),
                extra={"kind": "cambio", "before": rb.id, "after": ra.id, "stats": stats, "preview": png.name,
                       "uncertainty": CHANGE_UNCERTAINTY, "validated": False},
                created_by=getattr(user, "id", None),
            )
            db.add(record)
            db.flush()
            audit(db, "deteccion_cambios", user_id=user.id, target_type="data_record", target_id=record.id,
                  commit=False)
            _finish_run(db, run, "ok", {"record_id": record.id, **stats})
            return record
        except Exception as exc:
            db.rollback()
            _finish_run(db, run, "error", {"error": str(exc)[:500]})
            raise


def preview_path(record: DataRecord) -> Path:
    path = absolute_path(record).with_suffix(".png")
    if not path.is_file():
        raise FileNotFoundError("Vista previa no disponible.")
    return path
