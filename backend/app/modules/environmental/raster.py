"""Procesamiento raster de bajo consumo: malla común EPSG:4326, NDVI y detección de cambios.

Reglas de memoria (equipos de 4 GB):
- Nunca se lee una escena completa: solo la ventana del área y a resolución reducida
  (GDAL usa las vistas generales del COG).
- La malla de salida está limitada a MAX_DIM x MAX_DIM píxeles.
- Los cálculos se hacen por bloques de filas (ROW_BLOCK).
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import NotGeoreferencedWarning
from rasterio.transform import Affine, from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

WGS84 = "EPSG:4326"
MAX_DIM = 1600
ROW_BLOCK = 256
NDVI_SCALE = 10000
NDVI_NODATA = -32768
CHANGE_NODATA = 255
# Clases SCL de Sentinel-2 consideradas válidas: 4 vegetación, 5 suelo desnudo, 6 agua,
# 7 sin clasificar, 11 nieve/hielo. Se excluyen 0 sin datos, 1 saturado, 2 áreas oscuras,
# 3 sombras de nubes, 8-9 nubes, 10 cirros.
SCL_VALID = (4, 5, 6, 7, 11)
SCL_SNOW, SCL_WATER = 11, 6
KM_PER_DEG = 111.32


class GridError(ValueError):
    pass


@dataclass(frozen=True)
class Grid:
    bbox: tuple[float, float, float, float]  # minLon, minLat, maxLon, maxLat
    res: float                               # grados por píxel
    width: int
    height: int

    @property
    def transform(self) -> Affine:
        return from_origin(self.bbox[0], self.bbox[3], self.res, self.res)

    def pixel_area_km2(self) -> np.ndarray:
        """Área de cada fila de píxeles (km²), corrigiendo por latitud."""
        lats = self.bbox[3] - (np.arange(self.height) + 0.5) * self.res
        side = self.res * KM_PER_DEG
        return (side * side * np.cos(np.radians(lats))).astype("float64")


def make_grid(bbox: list[float] | tuple[float, ...], res: float) -> Grid:
    minx, miny, maxx, maxy = (float(v) for v in bbox)
    if not (minx < maxx and miny < maxy):
        raise GridError("El área debe tener mínimo < máximo en longitud y latitud.")
    width, height = math.ceil((maxx - minx) / res), math.ceil((maxy - miny) / res)
    if width > MAX_DIM or height > MAX_DIM:
        raise GridError(f"El área es demasiado grande para la resolución pedida ({width}x{height} px; máx. {MAX_DIM}).")
    # Se ajusta el borde para que la malla sea exacta.
    return Grid((minx, maxy - height * res, minx + width * res, maxy), res, width, height)


def read_to_grid(src: rasterio.io.DatasetReader, grid: Grid, *, resampling: Resampling,
                 scale: float = 1.0, offset: float = 0.0) -> np.ndarray:
    """Lee la parte de `src` que cubre la malla (a resolución reducida) y la reproyecta.
    Devuelve float32 con NaN donde no hay datos."""
    nodata = src.nodata if src.nodata is not None else 0
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    b = transform_bounds(WGS84, src.crs, *grid.bbox, densify_pts=21)
    win = from_bounds(*b, transform=src.transform)
    full = Window(0, 0, src.width, src.height)
    try:
        win = win.intersection(full).round_offsets().round_lengths()
    except Exception as exc:  # rasterio.errors.WindowError: sin intersección
        raise GridError("La escena no cubre el área de estudio.") from exc
    if win.width < 1 or win.height < 1:
        raise GridError("La escena no cubre el área de estudio.")
    # Factor de reducción: que el píxel leído sea ~ del tamaño del píxel de la malla.
    target_m = grid.res * KM_PER_DEG * 1000 * math.cos(math.radians((grid.bbox[1] + grid.bbox[3]) / 2))
    factor = max(1.0, target_m / abs(src.res[0]))
    out_h, out_w = max(1, round(win.height / factor)), max(1, round(win.width / factor))
    data = src.read(1, window=win, out_shape=(out_h, out_w), resampling=resampling)
    win_transform = src.window_transform(win) @ Affine.scale(win.width / out_w, win.height / out_h)
    raw = np.full((grid.height, grid.width), nodata, dtype=data.dtype)
    reproject(data, raw, src_transform=win_transform, src_crs=src.crs, src_nodata=nodata,
              dst_transform=grid.transform, dst_crs=WGS84, dst_nodata=nodata, resampling=resampling)
    for r0 in range(0, grid.height, ROW_BLOCK):
        blk = raw[r0:r0 + ROW_BLOCK]
        valid = blk != nodata
        out[r0:r0 + ROW_BLOCK][valid] = blk[valid].astype("float32") * scale + offset
    return out


SCL_SURFACE = (4, 5, 6)   # vegetación, suelo, agua: su reflectancia roja real siempre es > 0
OFFSET_MAX_NONPOSITIVE = 0.20


def choose_offset(red: np.ndarray, scl: np.ndarray | None, declared_offset: float) -> tuple[float, dict]:
    """Decide si aplicar el desplazamiento radiométrico declarado en los metadatos (p. ej. -0.1 de la
    línea base 04.00+). En la práctica algunos COG ya lo traen corregido aunque el metadato lo declare:
    si al aplicarlo más del 20 % de los píxeles de superficie quedan con reflectancia ≤ 0
    (físicamente imposible), se concluye que no corresponde y no se aplica. La decisión se registra."""
    info = {"declared_offset": declared_offset, "applied_offset": declared_offset, "reason": "metadatos"}
    if declared_offset >= 0:
        return declared_offset, info
    mask = np.isfinite(red)
    if scl is not None:
        mask &= np.isin(np.nan_to_num(scl, nan=0).astype("int16"), SCL_SURFACE)
    vals = red[mask]
    if vals.size == 0:
        return declared_offset, info
    frac = float(np.mean(vals + declared_offset <= 0))
    info["nonpositive_fraction_with_offset"] = round(frac, 3)
    if frac > OFFSET_MAX_NONPOSITIVE:
        info.update(applied_offset=0.0, reason=f"con el desplazamiento, {frac:.0%} de la superficie quedaría con "
                                               "reflectancia ≤ 0: los datos ya vienen corregidos")
        return 0.0, info
    return declared_offset, info


def compute_ndvi(red: np.ndarray, nir: np.ndarray, scl: np.ndarray | None) -> tuple[np.ndarray, dict]:
    """NDVI = (NIR - Rojo) / (NIR + Rojo) por bloques, con máscara de nubes/sombras (SCL)."""
    if red.shape != nir.shape or (scl is not None and scl.shape != red.shape):
        raise GridError("Las bandas no tienen la misma forma.")
    ndvi = np.full(red.shape, np.nan, dtype="float32")
    counts = {"total": 0, "valid": 0, "masked_scl": 0, "snow": 0, "water": 0, "nonpositive": 0}
    for r0 in range(0, red.shape[0], ROW_BLOCK):
        sl = slice(r0, r0 + ROW_BLOCK)
        r, n = red[sl], nir[sl]
        finite = np.isfinite(r) & np.isfinite(n)
        # Reflectancia ≤ 0 = ruido o sombra profunda: se excluye (evita NDVI = ±1 artificiales).
        positive = finite & (np.nan_to_num(r) > 0) & (np.nan_to_num(n) > 0)
        counts["nonpositive"] += int((finite & ~positive).sum())
        ok = positive
        counts["total"] += int(np.isfinite(r).sum())
        if scl is not None:
            s = scl[sl]
            good = np.isin(np.nan_to_num(s, nan=0).astype("int16"), SCL_VALID)
            counts["masked_scl"] += int((ok & ~good).sum())
            counts["snow"] += int((ok & good & (s == SCL_SNOW)).sum())
            counts["water"] += int((ok & good & (s == SCL_WATER)).sum())
            ok &= good
        with np.errstate(divide="ignore", invalid="ignore"):
            v = (n - r) / (n + r)
        blk = ndvi[sl]
        blk[ok] = np.clip(v[ok], -1, 1)
        counts["valid"] += int(ok.sum())
    total = max(counts["total"], 1)
    finite = ndvi[np.isfinite(ndvi)]
    stats = {
        "pixels_total": counts["total"], "pixels_valid": counts["valid"],
        "valid_pct": round(100 * counts["valid"] / total, 2),
        "cloud_shadow_masked_pct": round(100 * counts["masked_scl"] / total, 2),
        "nonpositive_reflectance_pct": round(100 * counts["nonpositive"] / total, 2),
        "snow_pct": round(100 * counts["snow"] / total, 2), "water_pct": round(100 * counts["water"] / total, 2),
        "ndvi_mean": round(float(finite.mean()), 4) if finite.size else None,
        "ndvi_p10": round(float(np.percentile(finite, 10)), 4) if finite.size else None,
        "ndvi_p90": round(float(np.percentile(finite, 90)), 4) if finite.size else None,
    }
    return ndvi, stats


def detect_change(before: np.ndarray, after: np.ndarray, grid: Grid, threshold: float) -> tuple[np.ndarray, dict]:
    """Clasifica diferencias de NDVI: 1 = disminución, 2 = aumento, 0 = sin cambio, 255 = sin datos."""
    if before.shape != after.shape or before.shape != (grid.height, grid.width):
        raise GridError("Los dos NDVI deben tener exactamente la misma malla.")
    if not 0.05 <= threshold <= 0.8:
        raise GridError("El umbral debe estar entre 0.05 y 0.8.")
    classes = np.full(before.shape, CHANGE_NODATA, dtype="uint8")
    area = grid.pixel_area_km2()
    acc = {"valid_km2": 0.0, "loss_km2": 0.0, "gain_km2": 0.0, "valid_px": 0, "sum_b": 0.0, "sum_a": 0.0}
    for r0 in range(0, before.shape[0], ROW_BLOCK):
        sl = slice(r0, r0 + ROW_BLOCK)
        b, a = before[sl], after[sl]
        ok = np.isfinite(b) & np.isfinite(a)
        d = np.where(ok, a - b, 0)
        c = classes[sl]
        c[ok] = 0
        c[ok & (d <= -threshold)] = 1
        c[ok & (d >= threshold)] = 2
        rows_area = area[sl][:, None]
        acc["valid_km2"] += float((ok * rows_area).sum())
        acc["loss_km2"] += float(((c == 1) * rows_area).sum())
        acc["gain_km2"] += float(((c == 2) * rows_area).sum())
        acc["valid_px"] += int(ok.sum())
        acc["sum_b"] += float(b[ok].sum())
        acc["sum_a"] += float(a[ok].sum())
    v = acc["valid_km2"] or 1.0
    n = acc["valid_px"] or 1
    stats = {
        "threshold": threshold, "common_valid_pct": round(100 * acc["valid_px"] / classes.size, 2),
        "common_valid_km2": round(acc["valid_km2"], 3),
        "ndvi_decrease_km2": round(acc["loss_km2"], 3), "ndvi_increase_km2": round(acc["gain_km2"], 3),
        "ndvi_decrease_pct": round(100 * acc["loss_km2"] / v, 2), "ndvi_increase_pct": round(100 * acc["gain_km2"] / v, 2),
        "ndvi_mean_before": round(acc["sum_b"] / n, 4) if acc["valid_px"] else None,
        "ndvi_mean_after": round(acc["sum_a"] / n, 4) if acc["valid_px"] else None,
    }
    return classes, stats


# ---------------------------------------------------------------- archivos
def _profile(grid: Grid, dtype: str, nodata) -> dict:
    return {"driver": "GTiff", "width": grid.width, "height": grid.height, "count": 1, "dtype": dtype,
            "crs": WGS84, "transform": grid.transform, "nodata": nodata, "compress": "deflate",
            "tiled": True, "blockxsize": 256, "blockysize": 256}


def write_ndvi(path: Path, ndvi: np.ndarray, grid: Grid) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **_profile(grid, "int16", NDVI_NODATA)) as dst:
        for r0 in range(0, grid.height, ROW_BLOCK):
            blk = ndvi[r0:r0 + ROW_BLOCK]
            out = np.where(np.isfinite(blk), np.round(blk * NDVI_SCALE), NDVI_NODATA).astype("int16")
            dst.write(out, 1, window=Window(0, r0, grid.width, out.shape[0]))


def read_ndvi(path: Path) -> tuple[np.ndarray, Grid]:
    with rasterio.open(path) as src:
        t = src.transform
        grid = Grid((t.c, t.f - src.height * abs(t.e), t.c + src.width * t.a, t.f), round(t.a, 12),
                    src.width, src.height)
        raw = src.read(1)
    ndvi = np.where(raw == NDVI_NODATA, np.nan, raw.astype("float32") / NDVI_SCALE).astype("float32")
    return ndvi, grid


def write_classes(path: Path, classes: np.ndarray, grid: Grid) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **_profile(grid, "uint8", CHANGE_NODATA)) as dst:
        dst.write(classes, 1)


def _ramp(v: np.ndarray) -> np.ndarray:
    """Paleta NDVI: <0 azul grisáceo, 0-0.2 marrón, 0.2-0.5 amarillo-verde, >0.5 verde oscuro."""
    stops = np.array([-1.0, 0.0, 0.2, 0.5, 1.0])
    cols = np.array([[90, 110, 140], [165, 120, 80], [215, 200, 90], [110, 175, 70], [20, 100, 40]], dtype="float32")
    return np.stack([np.interp(v, stops, cols[:, i]) for i in range(3)], axis=-1)


def write_png(path: Path, rgba: np.ndarray) -> None:
    """PNG RGBA con el driver PNG de GDAL (sin Pillow)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w, _ = rgba.shape
    # El PNG no lleva georreferencia a propósito: el mapa lo ubica con el bbox del registro.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(path, "w", driver="PNG", width=w, height=h, count=4, dtype="uint8") as dst:
            dst.write(np.moveaxis(rgba, -1, 0))


def ndvi_rgba(ndvi: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*ndvi.shape, 4), dtype="uint8")
    for r0 in range(0, ndvi.shape[0], ROW_BLOCK):
        blk = ndvi[r0:r0 + ROW_BLOCK]
        ok = np.isfinite(blk)
        rgb = _ramp(np.nan_to_num(blk, nan=0.0))
        out = rgba[r0:r0 + ROW_BLOCK]
        out[..., :3] = rgb.astype("uint8")
        out[..., 3] = np.where(ok, 210, 0)
    return rgba


def change_rgba(classes: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*classes.shape, 4), dtype="uint8")
    rgba[classes == 1] = (200, 50, 50, 230)    # disminución de NDVI
    rgba[classes == 2] = (40, 150, 90, 230)    # aumento de NDVI
    rgba[classes == 0] = (200, 200, 200, 60)   # sin cambio (tenue)
    return rgba
