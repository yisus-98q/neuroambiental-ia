"""Variables del terreno derivadas SOLO del DEM (sin datos nuevos), justificadas físicamente:

- curvatura (laplaciano del DEM suavizado, 1/100 m): negativa = cóncava (vaguadas, convergencia del flujo),
  positiva = convexa (crestas). Controla dónde se concentra el agua y el material.
- TPI (índice de posición topográfica, m): elevación menos la media en un radio ≈300 m. Negativo = fondo de
  valle; positivo = loma. Distingue laderas altas (caídas) de fondos y abanicos (depósitos de flujos).
- distancia a cauce (m): los flujos/huaycos siguen y depositan junto a los cauces. La red de cauces se
  obtiene del DEM: relleno de depresiones (priority-flood con épsilon), dirección D8 y acumulación; una celda
  es cauce si drena ≥ CHANNEL_AREA_KM2. La hidrología se calcula a ≈70 m para caber en 4 GB de RAM.
Limitaciones: la red derivada no es la red oficial (ANA); el umbral de área define cuántos cauces aparecen.
"""
from __future__ import annotations

import heapq
import math

import numpy as np
from scipy import ndimage

from app.modules.neuro3d import dem as demlib

HYDRO_TARGET_M = 70.0
CHANNEL_AREA_KM2 = 0.25
TPI_RADIUS_M = 300.0
EPS = 1e-4  # m: pendiente mínima impuesta en zonas rellenadas para que drenen

DESCRIPTIONS = {
    "pendiente_deg": "Pendiente (°) del DEM.",
    "elevacion_m": "Elevación (m). Puede reflejar el sesgo de muestreo del inventario.",
    "curvatura": "Laplaciano del DEM suavizado (1/100 m): negativo = cóncavo (vaguada), positivo = convexo (cresta).",
    "tpi_m": f"Posición topográfica (m): elevación menos la media en ≈{TPI_RADIUS_M:.0f} m; negativo = fondo de valle.",
    "dist_cauce_m": f"Distancia (m) a la red de cauces derivada del DEM (área drenada ≥ {CHANNEL_AREA_KM2} km², "
                    f"hidrología a ≈{HYDRO_TARGET_M:.0f} m).",
    "ndvi_anillo": "NDVI medio (Sentinel-2) en un anillo de 100–300 m alrededor de la celda; sin dato si menos del "
                   "60 % de los píxeles del anillo son válidos (nubes, nieve, agua). Es la cobertura ACTUAL, posterior "
                   "a la mayoría de los eventos: no es la condición previa.",
}

_OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def fill_depressions(z: np.ndarray) -> np.ndarray:
    """Priority-flood con épsilon (Barnes et al., 2014): sin depresiones cerradas y con drenaje en llanos."""
    h, w = z.shape
    zf = z.astype("float64").ravel().tolist()
    closed = bytearray(h * w)
    heap: list[tuple[float, int]] = []
    for r in range(h):
        for c in (0, w - 1):
            i = r * w + c
            if not closed[i]:
                closed[i] = 1
                heap.append((zf[i], i))
    for c in range(1, w - 1):
        for r in (0, h - 1):
            i = r * w + c
            if not closed[i]:
                closed[i] = 1
                heap.append((zf[i], i))
    heapq.heapify(heap)
    pop, push = heapq.heappop, heapq.heappush
    while heap:
        e, i = pop(heap)
        r, c = divmod(i, w)
        for dr, dc in _OFFS:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                j = rr * w + cc
                if not closed[j]:
                    closed[j] = 1
                    if zf[j] <= e:
                        zf[j] = e + EPS
                    push(heap, (zf[j], j))
    return np.asarray(zf, dtype="float64").reshape(h, w)


def d8_receivers(z: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Índice plano de la celda vecina de mayor descenso por distancia (-1 si no hay descenso)."""
    h, w = z.shape
    pad = np.pad(z, 1, constant_values=np.inf)
    best = np.zeros((h, w))
    recv = np.full((h, w), -1, dtype=np.int64)
    rows, cols = np.indices((h, w))
    for dr, dc in _OFFS:
        nb = pad[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]
        drop = (z - nb) / math.hypot(dr * dy, dc * dx)
        better = drop > best
        best = np.where(better, drop, best)
        recv = np.where(better, (rows + dr) * w + (cols + dc), recv)
    return recv.ravel()


def flow_accumulation(zfilled: np.ndarray, recv: np.ndarray) -> np.ndarray:
    """Número de celdas que drenan a cada celda (incluida ella misma)."""
    order = np.argsort(-zfilled.ravel(), kind="stable").tolist()
    acc = [1] * len(order)
    rl = recv.tolist()
    for i in order:
        r = rl[i]
        if r >= 0:
            acc[r] += acc[i]
    return np.asarray(acc, dtype="float64").reshape(zfilled.shape)


def compute(arr: np.ndarray, bbox) -> dict[str, np.ndarray]:
    """Pila de variables a la resolución del DEM (float32)."""
    dxs, dy = demlib._spacing(bbox, arr)
    dx = float(np.mean(dxs))
    z = np.where(np.isfinite(arr), arr, np.nanmax(arr)).astype("float64")
    out = {"pendiente_deg": demlib.slope_deg(arr, bbox).astype("float32"), "elevacion_m": arr.astype("float32")}

    zs = ndimage.gaussian_filter(z, sigma=1.0)
    d2x = np.gradient(np.gradient(zs, dx, axis=1), dx, axis=1)
    d2y = np.gradient(np.gradient(zs, dy, axis=0), dy, axis=0)
    out["curvatura"] = ((d2x + d2y) * 100.0).astype("float32")
    del zs, d2x, d2y

    k = max(3, int(round(2 * TPI_RADIUS_M / dx)) | 1)
    out["tpi_m"] = (z - ndimage.uniform_filter(z, size=k, mode="nearest")).astype("float32")

    f = max(1, int(round(HYDRO_TARGET_M / dx)))
    h, w = z.shape
    hc, wc = h // f, w // f
    zc = z[:hc * f, :wc * f].reshape(hc, f, wc, f).mean(axis=(1, 3))
    filled = fill_depressions(zc)
    acc = flow_accumulation(filled, d8_receivers(filled, dx * f, dy * f))
    cell_km2 = dx * f * dy * f / 1e6
    channels = acc * cell_km2 >= CHANNEL_AREA_KM2
    dist_c = ndimage.distance_transform_edt(~channels, sampling=(dy * f, dx * f)).astype("float32")
    ri = np.minimum(np.arange(h) // f, hc - 1)
    ci = np.minimum(np.arange(w) // f, wc - 1)
    out["dist_cauce_m"] = dist_c[np.ix_(ri, ci)]
    return out


def ring_mean(values: np.ndarray, dx: float, dy: float, inner_m: float = 100.0, outer_m: float = 300.0,
              min_valid: float = 0.6) -> np.ndarray:
    """Media de los píxeles válidos (finitos) en un anillo; NaN si la fracción válida es < min_valid."""
    rx, ry = int(math.ceil(outer_m / dx)), int(math.ceil(outer_m / dy))
    yy, xx = np.mgrid[-ry:ry + 1, -rx:rx + 1]
    d = np.hypot(xx * dx, yy * dy)
    kernel = ((d >= inner_m) & (d <= outer_m)).astype("float32")
    valid = np.isfinite(values)
    v = np.where(valid, values, 0).astype("float32")
    s = ndimage.convolve(v, kernel, mode="constant", cval=0.0)
    n = ndimage.convolve(valid.astype("float32"), kernel, mode="constant", cval=0.0)
    frac = n / kernel.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(frac >= min_valid, s / np.maximum(n, 1), np.nan)
    return out.astype("float32")
