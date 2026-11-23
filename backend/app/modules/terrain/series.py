"""NEUROTERRAIN: análisis de series de desplazamiento (numpy puro, sin red).

Todo lo que sale de aquí es un INDICADOR EXPERIMENTAL por umbrales. No es una predicción de falla ni
sustituye el criterio geotécnico. Los umbrales por defecto son valores de EJEMPLO configurables.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

AVISO = "Indicador experimental por umbrales; no es una predicción de falla ni sustituye el criterio geotécnico."
ROTULO_UMBRALES = ("Valores de EJEMPLO configurables, no son umbrales oficiales ni normativos. "
                   "Defínalos según la unidad, el sensor y el criterio geotécnico del sitio.")
MIN_POINTS = 5
MAX_UI_POINTS = 2000
DAY = 86400.0


class SeriesError(ValueError):
    pass


@dataclass
class Config:
    window_days: float = 30.0        # ventana «reciente» para velocidad y aceleración
    vel_threshold: float = 0.05      # unidad/día por debajo de la cual se considera «estable» (EJEMPLO)
    acc_ratio: float = 1.5           # velocidad reciente / velocidad previa para «acelerando» (EJEMPLO)
    k_mad: float = 6.0               # saltos: |residuo| > k · 1.4826 · MAD
    max_points: int = MAX_UI_POINTS

    def validate(self) -> "Config":
        if not (0 < self.window_days <= 36500):
            raise SeriesError("window_days debe estar entre 0 y 36500 días.")
        if not (self.vel_threshold > 0 and math.isfinite(self.vel_threshold)):
            raise SeriesError("El umbral de velocidad debe ser > 0.")
        if not (1.0 < self.acc_ratio <= 100):
            raise SeriesError("El cociente de aceleración debe estar entre 1 y 100.")
        if not (2.0 <= self.k_mad <= 50):
            raise SeriesError("k_mad debe estar entre 2 y 50.")
        if not (10 <= self.max_points <= MAX_UI_POINTS):
            raise SeriesError(f"max_points debe estar entre 10 y {MAX_UI_POINTS}.")
        return self


def linfit(t: np.ndarray, y: np.ndarray) -> dict | None:
    """Regresión lineal y = a + b·t. Devuelve pendiente, error estándar de la pendiente y R²."""
    n = len(t)
    if n < 3:
        return None
    tm, ym = t.mean(), y.mean()
    sxx = float(((t - tm) ** 2).sum())
    if sxx <= 0:
        return None
    b = float(((t - tm) * (y - ym)).sum() / sxx)
    a = float(ym - b * tm)
    res = y - (a + b * t)
    ss_res = float((res ** 2).sum())
    ss_tot = float(((y - ym) ** 2).sum())
    se = math.sqrt(ss_res / (n - 2) / sxx) if n > 2 else float("nan")
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"slope": b, "intercept": a, "se": se, "r2": r2, "n": n}


def _mad(x: np.ndarray) -> float:
    return float(np.median(np.abs(x - np.median(x))))


def detect_jumps(t: np.ndarray, y: np.ndarray, k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Detecta saltos puntuales en los incrementos.

    Para cada incremento d_i se compara con lo esperado según la velocidad mediana local (ventana móvil
    de ±5 incrementos). Si el residuo supera k·1.4826·MAD (con un piso relativo al rango) se marca. Una
    tendencia suave (incluso acelerada) no genera saltos; un escalón o un pico aislado sí.
    Devuelve (índices de punto afectado, residuos por incremento, incrementos corregidos).
    """
    dt = np.diff(t)
    d = np.diff(y)
    rate = d / dt
    m = len(rate)
    half = 5
    local = np.empty(m)
    for i in range(m):
        local[i] = np.median(rate[max(0, i - half): i + half + 1])
    expected = local * dt
    resid = d - expected
    span = float(y.max() - y.min())
    scale = max(1.4826 * _mad(resid), 1e-3 * span, 1e-12)
    flagged = np.abs(resid) > k * scale
    corrected = np.where(flagged, expected, d)
    return np.flatnonzero(flagged) + 1, resid, corrected


def _window_velocity(t: np.ndarray, y: np.ndarray, lo: float, hi: float) -> dict | None:
    sel = (t > lo) & (t <= hi)
    return linfit(t[sel], y[sel]) if sel.sum() >= 3 else None


def _downsample(n: int, keep: set[int], max_points: int) -> list[int]:
    """Índices a devolver a la UI (≤ max_points); siempre incluye extremos y anomalías."""
    if n <= max_points:
        return list(range(n))
    keep = set(sorted(keep)[: max_points // 2])  # nunca más de la mitad del cupo en anomalías
    base = np.linspace(0, n - 1, max_points - len(keep), dtype=int).tolist()
    return sorted(set(base) | keep)


def classify(vel_recent: float | None, vel_prev: float | None, acc_significant: bool, cfg: Config) -> dict:
    """Clasificación cualitativa EXPERIMENTAL: estable / en_movimiento / acelerando."""
    if vel_recent is None:
        return {"estado": "indeterminado", "motivo": "No hay datos suficientes en la ventana reciente."}
    mag = abs(vel_recent)
    if mag < cfg.vel_threshold:
        return {"estado": "estable", "motivo": f"|velocidad reciente| = {mag:.4g} < umbral de ejemplo {cfg.vel_threshold:g}."}
    prev = abs(vel_prev) if vel_prev is not None else None
    if prev is not None and acc_significant and mag > prev and (prev == 0 or mag / prev >= cfg.acc_ratio):
        ratio = "sin velocidad previa" if prev == 0 else f"cociente {mag / prev:.2f} ≥ {cfg.acc_ratio:g}"
        return {"estado": "acelerando",
                "motivo": f"Velocidad reciente {mag:.4g} frente a {prev:.4g} en la ventana previa ({ratio}), diferencia significativa."}
    return {"estado": "en_movimiento",
            "motivo": f"|velocidad reciente| = {mag:.4g} ≥ umbral de ejemplo {cfg.vel_threshold:g}, sin aceleración significativa."}


def analyze(epoch_s: list[float], values: list[float], cfg: Config, unit: str = "") -> dict:
    """Analiza una serie ya ordenada y sin duplicados (epoch en segundos, valores numéricos)."""
    cfg.validate()
    t_abs = np.asarray(epoch_s, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    n = len(y)
    if n < MIN_POINTS:
        raise SeriesError(f"Serie insuficiente: {n} mediciones (mínimo {MIN_POINTS}).")
    if not (np.isfinite(y).all() and np.all(np.diff(t_abs) > 0)):
        raise SeriesError("La serie debe tener valores finitos y fechas estrictamente crecientes.")
    t = (t_abs - t_abs[0]) / DAY  # días desde la primera medición
    total_days = float(t[-1])
    notes: list[str] = []

    jump_idx, _, corrected = detect_jumps(t, y, cfg.k_mad)
    y_adj = np.concatenate([[y[0]], y[0] + np.cumsum(corrected)])
    if len(jump_idx):
        notes.append(f"Se detectaron {len(jump_idx)} salto(s)/anomalía(s); velocidad, aceleración y clasificación "
                     "usan la serie con los saltos neutralizados (la serie original se muestra tal cual).")

    full = linfit(t, y_adj)
    full_raw = linfit(t, y)
    win = min(cfg.window_days, total_days / 2.0)
    if win < cfg.window_days:
        notes.append(f"La serie dura {total_days:.1f} días: la ventana efectiva se redujo de {cfg.window_days:g} a {win:.1f} días.")
    t_end = float(t[-1])
    recent = _window_velocity(t, y_adj, t_end - win, t_end)
    prev = _window_velocity(t, y_adj, t_end - 2 * win, t_end - win)
    if recent is None:
        notes.append("Menos de 3 mediciones en la ventana reciente: sin velocidad reciente.")
    if prev is None:
        notes.append("Menos de 3 mediciones en la ventana previa: no se evalúa aceleración por ventanas.")

    acc = acc_se = None
    significant = False
    if recent and prev:
        acc = (recent["slope"] - prev["slope"]) / win
        diff_se = math.sqrt(recent["se"] ** 2 + prev["se"] ** 2)
        acc_se = diff_se / win
        significant = (abs(recent["slope"]) > abs(prev["slope"])
                       and abs(recent["slope"] - prev["slope"]) > 3 * diff_se)
    quad = None
    if n >= 8:
        c2, _c1, _c0 = np.polyfit(t - t.mean(), y_adj, 2)
        quad = float(2 * c2)  # aceleración constante equivalente (unidad/día²)

    cls = classify(recent["slope"] if recent else None, prev["slope"] if prev else None, significant, cfg)
    if cls["estado"] == "indeterminado" and full:
        cls = classify(full["slope"], None, False, cfg)
        cls["motivo"] += " (se usó la velocidad de la ventana completa)."

    anomalies = [{"index": int(i), "observed_at_epoch": float(t_abs[i]), "value": float(y[i]),
                  "increment": float(y[i] - y[i - 1])} for i in jump_idx]
    keep = {0, n - 1, *[int(i) for i in jump_idx]}
    flag = set(int(i) for i in jump_idx)
    idx = _downsample(n, keep, cfg.max_points)
    cumulative = y - y[0]

    def _v(fit: dict | None) -> dict | None:
        return None if fit is None else {"velocidad": fit["slope"], "error_estandar": fit["se"], "r2": fit["r2"],
                                         "n": fit["n"], "unidad": f"{unit}/día" if unit else "unidad/día"}

    return {
        "n_mediciones": n,
        "n_puntos_devueltos": len(idx),
        "submuestreada": len(idx) < n,
        "duracion_dias": total_days,
        "desplazamiento_acumulado": float(cumulative[-1]),
        "desplazamiento_acumulado_sin_saltos": float(y_adj[-1] - y_adj[0]),
        "velocidad_total": _v(full),
        "velocidad_total_con_saltos": _v(full_raw),
        "ventana_dias": float(win),
        "velocidad_reciente": _v(recent),
        "velocidad_previa": _v(prev),
        "aceleracion": None if acc is None else {
            "valor": acc, "error_estandar": acc_se, "significativa": bool(significant),
            "unidad": f"{unit}/día²" if unit else "unidad/día²",
            "metodo": "(velocidad reciente − velocidad previa) / ventana"},
        "aceleracion_cuadratica": quad,
        "anomalias": anomalies,
        "clasificacion": {**cls, "experimental": True, "aviso": AVISO},
        "umbrales": {**asdict(cfg), "rotulo": ROTULO_UMBRALES},
        "notas": notes,
        "aviso": AVISO,
        "puntos": [{"t": float(t_abs[i]), "v": float(y[i]), "d": float(cumulative[i]), "a": i in flag} for i in idx],
    }
