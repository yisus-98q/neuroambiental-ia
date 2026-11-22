"""NEURO 3D LAB: cálculo puro sobre el DEM (teselas, mosaico, pendiente, trayectoria D8). Sin base de datos ni red.

Todo se calcula sobre una malla EPSG:4326 (filas de norte a sur). El tamaño del píxel en metros se corrige
por latitud: dx = dlon * 111 320 * cos(lat), dy = dlat * 110 574.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from app.modules.environmental import raster

M_PER_DEG_LON = 111_320.0
M_PER_DEG_LAT = 110_574.0
MAX_VIEWER_PX = 512
DEM_NODATA = -9999.0
SLOPE_BINS = (0.0, 15.0, 25.0, 35.0, 90.01)
SLOPE_LABELS = ("0-15°", "15-25°", "25-35°", ">35°")
MAX_PATH_STEPS = 2000
FLOW_DISCLAIMER = ("Escenario demostrativo simplificado (camino de máxima pendiente). "
                   "No es una simulación geotécnica ni predice un evento.")


class DemError(ValueError):
    """Entrada inválida para el DEM o el escenario (se responde 422)."""


@dataclass(frozen=True)
class Tile:
    lat: int   # esquina inferior-izquierda
    lon: int

    @property
    def name(self) -> str:
        ns, ew = ("N" if self.lat >= 0 else "S"), ("E" if self.lon >= 0 else "W")
        return f"Copernicus_DSM_COG_10_{ns}{abs(self.lat):02d}_00_{ew}{abs(self.lon):03d}_00_DEM"


def tiles_for_bbox(bbox) -> list[Tile]:
    """Teselas de 1x1 grado (GLO-30) que cubren el bbox. Un borde exactamente entero no suma otra tesela."""
    minx, miny, maxx, maxy = (float(v) for v in bbox)
    eps = 1e-9
    lats = range(math.floor(miny), math.floor(maxy - eps) + 1)
    lons = range(math.floor(minx), math.floor(maxx - eps) + 1)
    return [Tile(la, lo) for la in lats for lo in lons]


def make_dem_grid(bbox, res: float) -> raster.Grid:
    try:
        grid = raster.make_grid(bbox, res)
    except raster.GridError as exc:
        raise DemError(str(exc)) from exc
    if grid.width > MAX_VIEWER_PX or grid.height > MAX_VIEWER_PX:
        raise DemError(f"La malla resultante ({grid.width}x{grid.height} px) supera {MAX_VIEWER_PX}x{MAX_VIEWER_PX}: "
                       "reduzca el área o use una resolución más gruesa.")
    return grid


def read_tile(src, grid: raster.Grid) -> np.ndarray:
    """Lee una tesela sobre la malla común con el warper de GDAL (usa las vistas generales del COG).
    No se usa raster.read_to_grid: estima el factor de reducción con src.res en metros y falla con
    fuentes en grados (EPSG:4326), que es el caso de GLO-30."""
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    reproject(rasterio.band(src, 1), out, dst_transform=grid.transform, dst_crs=raster.WGS84,
              src_nodata=src.nodata, dst_nodata=float("nan"), resampling=Resampling.average)
    return out


def mosaic(parts: list[np.ndarray]) -> np.ndarray:
    """Combina lecturas de teselas sobre la misma malla: el primer valor válido gana."""
    out = parts[0].copy()
    for p in parts[1:]:
        hole = np.isnan(out)
        out[hole] = p[hole]
    return out


# ---------------------------------------------------------------- archivos
def write_dem(path: Path, dem: np.ndarray, grid: raster.Grid) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = np.where(np.isfinite(dem), dem, DEM_NODATA).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", width=grid.width, height=grid.height, count=1, dtype="float32",
                       crs=raster.WGS84, transform=grid.transform, nodata=DEM_NODATA, compress="deflate") as dst:
        dst.write(out, 1)


def read_dem(path: Path, max_size: int | None = None) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Lee el DEM (opcionalmente remuestreado con promedio a <= max_size). NaN donde no hay dato."""
    with rasterio.open(path) as src:
        t = src.transform
        bbox = (t.c, t.f - src.height * abs(t.e), t.c + src.width * t.a, t.f)
        shape = (src.height, src.width)
        if max_size and max(shape) > max_size:
            k = max_size / max(shape)
            shape = (max(2, round(src.height * k)), max(2, round(src.width * k)))
        data = src.read(1, out_shape=shape, resampling=Resampling.average)
    arr = data.astype("float32")
    arr[arr <= DEM_NODATA + 1] = np.nan
    return arr, bbox


def cell_size(bbox, arr: np.ndarray) -> tuple[float, float]:
    return (bbox[2] - bbox[0]) / arr.shape[1], (bbox[3] - bbox[1]) / arr.shape[0]


def _spacing(bbox, arr: np.ndarray) -> tuple[np.ndarray, float]:
    dlon, dlat = cell_size(bbox, arr)
    lats = bbox[3] - (np.arange(arr.shape[0]) + 0.5) * dlat
    return dlon * M_PER_DEG_LON * np.cos(np.radians(lats)), dlat * M_PER_DEG_LAT  # dx por fila (m), dy (m)


# ---------------------------------------------------------------- pendiente
def slope_deg(dem: np.ndarray, bbox) -> np.ndarray:
    """Pendiente (grados) por diferencias finitas centrales; NaN donde falta dato en el entorno."""
    dx, dy = _spacing(bbox, dem)
    with np.errstate(invalid="ignore"):
        gx = np.gradient(dem, axis=1) / dx[:, None]
        gy = np.gradient(dem, axis=0) / dy
        return np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


def slope_stats(slope: np.ndarray) -> dict:
    v = slope[np.isfinite(slope)]
    if v.size == 0:
        return {"classes": [], "mean_deg": None, "max_deg": None}
    classes = []
    for lo, hi, label in zip(SLOPE_BINS[:-1], SLOPE_BINS[1:], SLOPE_LABELS):
        n = int(((v >= lo) & (v < hi)).sum())
        classes.append({"label": label, "pct": round(100 * n / v.size, 2), "pixels": n})
    return {"classes": classes, "mean_deg": round(float(v.mean()), 2), "max_deg": round(float(v.max()), 2)}


def elevation_stats(dem: np.ndarray) -> dict:
    v = dem[np.isfinite(dem)]
    if v.size == 0:
        raise DemError("El DEM no tiene píxeles válidos.")
    return {"min": round(float(v.min()), 1), "max": round(float(v.max()), 1), "mean": round(float(v.mean()), 1),
            "valid_pct": round(100 * v.size / dem.size, 2)}


# ---------------------------------------------------------------- trayectoria D8
def flow_path(dem: np.ndarray, bbox, lon: float, lat: float, max_steps: int = MAX_PATH_STEPS) -> dict:
    """Camino de máxima pendiente (D8) desde (lon, lat) hasta un mínimo local, el borde o max_steps."""
    h, w = dem.shape
    dlon, dlat = cell_size(bbox, dem)
    col, row = int(math.floor((lon - bbox[0]) / dlon)), int(math.floor((bbox[3] - lat) / dlat))
    if not (0 <= col < w and 0 <= row < h):
        raise DemError("El punto está fuera del DEM cargado.")
    if not np.isfinite(dem[row, col]):
        raise DemError("El punto cae en una celda sin dato de elevación.")
    dx_row, dy = _spacing(bbox, dem)

    def coord(r: int, c: int) -> list[float]:
        return [round(bbox[0] + (c + 0.5) * dlon, 6), round(bbox[3] - (r + 0.5) * dlat, 6), round(float(dem[r, c]), 1)]

    path, length_m, reason = [coord(row, col)], 0.0, "max_pasos"
    for _ in range(max_steps):
        if row in (0, h - 1) or col in (0, w - 1):
            reason = "borde"
            break
        best, best_g, best_d = None, 0.0, 0.0
        z = dem[row, col]
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == dc == 0:
                    continue
                zn = dem[row + dr, col + dc]
                if not np.isfinite(zn) or zn >= z:
                    continue
                dist = math.hypot(dc * dx_row[row], dr * dy)
                g = float(z - zn) / dist
                if g > best_g:
                    best, best_g, best_d = (dr, dc), g, dist
        if best is None:
            reason = "minimo_local"
            break
        row, col, length_m = row + best[0], col + best[1], length_m + best_d
        path.append(coord(row, col))
    drop = path[0][2] - path[-1][2]
    return {"path": path, "length_km": round(length_m / 1000, 3), "drop_m": round(drop, 1), "steps": len(path) - 1,
            "mean_slope_deg": round(math.degrees(math.atan(drop / length_m)), 1) if length_m > 0 else 0.0,
            "end_reason": reason, "start_elevation_m": path[0][2], "end_elevation_m": path[-1][2]}
