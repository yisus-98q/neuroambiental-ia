"""Validación de la susceptibilidad a movimientos en masa con el inventario REAL de INGEMMET.

Método (deliberadamente sencillo y verificable):
1. Presencias: eventos del inventario (tipos de movimiento en masa) dentro del DEM.
2. Ausencias: celdas aleatorias del DEM con dato y a ≥ `min_dist_m` de todo evento (pseudo-ausencias;
   «sin evento inventariado» NO significa «sin peligro»: el inventario es incompleto).
3. Variables: pendiente (°) y elevación (m) del DEM GLO-30.
4. Evaluación con VALIDACIÓN CRUZADA ESPACIAL por bloques (GroupKFold): los puntos de prueba están en
   bloques geográficos distintos a los de entrenamiento, para no inflar las métricas por autocorrelación.
   Se informa también la validación aleatoria, solo para mostrar cuánto la infla.
5. El índice heurístico (pendiente/45°) se evalúa SIN entrenar: su AUC es una validación directa.
Nada aquí convierte un modelo en «validado»: eso lo decide un administrador con esta evidencia.
"""
from __future__ import annotations

import csv
import io
import json
import math

import numpy as np
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.modules.neuro3d import dem as demlib

MASS_MOVEMENT_KEYWORDS = ("desliz", "derrumbe", "caida", "caída", "huayco", "huaico", "flujo", "avalancha",
                          "reptac", "movimiento", "vuelco", "alud")
HEURISTIC_SATURATION_DEG = 45.0


class ValidationError(ValueError):
    pass


def _is_mass_movement(props: dict) -> bool:
    """INGEMMET codifica el tipo (p. ej. «1000|1300»). El grupo 1000 corresponde a movimientos en masa en la
    clasificación del Proyecto Multinacional Andino que usa INGEMMET (1100 caídas, 1300 deslizamientos,
    1500 flujos —incluye huaycos—…; correspondencia exacta a confirmar con INGEMMET). También se aceptan
    descripciones en texto por si otra fuente usa nombres."""
    code = str(props.get("TIP_PELIGRO") or "")
    if code.split("|")[0] == "1000":
        return True
    text = f"{code} {props.get('NOM_PELIGRO') or ''}".lower()
    return any(k in text for k in MASS_MOVEMENT_KEYWORDS)


def event_cells(fc: dict, arr: np.ndarray, bbox, only_mass_movement: bool = True) -> tuple[np.ndarray, dict]:
    h, w = arr.shape
    dlon, dlat = demlib.cell_size(bbox, arr)
    cells, skipped = set(), {"fuera_del_dem": 0, "otro_tipo": 0, "sin_dato": 0}
    for f in fc.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        if only_mass_movement and not _is_mass_movement(f.get("properties") or {}):
            skipped["otro_tipo"] += 1
            continue
        lon, lat = g["coordinates"][:2]
        c, r = int(math.floor((lon - bbox[0]) / dlon)), int(math.floor((bbox[3] - lat) / dlat))
        if not (0 <= r < h and 0 <= c < w):
            skipped["fuera_del_dem"] += 1
        elif not np.isfinite(arr[r, c]):
            skipped["sin_dato"] += 1
        else:
            cells.add((r, c))  # varios eventos en la misma celda cuentan una vez
    return np.array(sorted(cells), dtype=int).reshape(-1, 2), skipped


def build_points(arr: np.ndarray, bbox, presences: np.ndarray, ratio: int, min_dist_m: float, seed: int,
                 elevation_range: tuple[float, float] | None = None):
    if len(presences) < 20:
        raise ValidationError(f"Muy pocos eventos útiles dentro del DEM ({len(presences)}; mínimo 20).")
    mask = np.zeros(arr.shape, dtype=bool)
    mask[presences[:, 0], presences[:, 1]] = True
    dx = float(np.mean(demlib._spacing(bbox, arr)[0]))
    dist_cells = ndimage.distance_transform_edt(~mask)
    eligible = np.isfinite(arr) & (dist_cells * dx >= min_dist_m)
    if elevation_range is not None:
        # Corrección del sesgo de muestreo del inventario: ausencias solo en el rango de elevación de los eventos.
        with np.errstate(invalid="ignore"):
            eligible &= (arr >= elevation_range[0]) & (arr <= elevation_range[1])
    cand = np.argwhere(eligible)
    n_abs = min(len(cand), ratio * len(presences))
    if n_abs < len(presences):
        raise ValidationError("No hay suficientes celdas lejos de los eventos para generar ausencias.")
    rng = np.random.default_rng(seed)
    absences = cand[rng.choice(len(cand), size=n_abs, replace=False)]
    pts = np.vstack([presences, absences])
    y = np.r_[np.ones(len(presences), int), np.zeros(n_abs, int)]
    return pts, y


def spatial_groups(pts: np.ndarray, shape: tuple[int, int], blocks: int) -> np.ndarray:
    h, w = shape
    return (pts[:, 0] * blocks // h) * blocks + (pts[:, 1] * blocks // w)


def _cv_auc(model_factory, X, y, splitter, groups=None) -> dict:
    aucs = []
    for tr, te in splitter.split(X, y, groups):
        if len(set(y[te])) < 2 or len(set(y[tr])) < 2:
            continue
        m = model_factory()
        m.fit(X[tr], y[tr])
        aucs.append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
    if not aucs:
        return {"auc_mean": None, "auc_sd": None, "folds": 0}
    return {"auc_mean": round(float(np.mean(aucs)), 4), "auc_sd": round(float(np.std(aucs)), 4), "folds": len(aucs)}


def evaluate(arr: np.ndarray, bbox, fc: dict, *, ratio: int = 3, min_dist_m: float = 300.0, blocks: int = 4,
             seed: int = 42, only_mass_movement: bool = True) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
    presences, skipped = event_cells(fc, arr, bbox, only_mass_movement)
    if len(presences) < 20:
        raise ValidationError(f"Muy pocos eventos útiles dentro del DEM ({len(presences)}; mínimo 20).")
    slope = demlib.slope_deg(arr, bbox)
    ev_elev = arr[presences[:, 0], presences[:, 1]]
    band = (float(np.percentile(ev_elev, 5)), float(np.percentile(ev_elev, 95)))

    def assess(elevation_range):
        pts, y = build_points(arr, bbox, presences, ratio, min_dist_m, seed, elevation_range)
        X = np.c_[slope[pts[:, 0], pts[:, 1]], arr[pts[:, 0], pts[:, 1]]].astype("float64")
        ok = np.isfinite(X).all(axis=1)
        X, y, pts = X[ok], y[ok], pts[ok]
        groups = spatial_groups(pts, arr.shape, blocks)
        k = min(5, len(set(groups.tolist())))
        if k < 3:
            raise ValidationError("El área es demasiado pequeña para una validación espacial por bloques.")
        logistic = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))  # noqa: E731
        forest = lambda: RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=5,  # noqa: E731
                                                n_jobs=1, random_state=seed)
        spatial, rand = GroupKFold(n_splits=k), StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        res = {
            "n_presencias": int(y.sum()), "n_ausencias": int(len(y) - y.sum()), "folds_espaciales": k,
            "auc_heuristico_pendiente": round(float(roc_auc_score(y, np.clip(X[:, 0] / HEURISTIC_SATURATION_DEG,
                                                                            0, 1))), 4),
            "auc_solo_elevacion_baja": round(float(roc_auc_score(y, -X[:, 1])), 4),
            "regresion_logistica": {"espacial": _cv_auc(logistic, X, y, spatial, groups),
                                    "aleatoria_referencia": _cv_auc(logistic, X, y, rand)},
            "bosque_aleatorio": {"espacial": _cv_auc(forest, X, y, spatial, groups),
                                 "aleatoria_referencia": _cv_auc(forest, X, y, rand)},
            "pendiente_media_eventos": round(float(X[y == 1, 0].mean()), 2),
            "pendiente_media_ausencias": round(float(X[y == 0, 0].mean()), 2),
            "elevacion_media_eventos": round(float(X[y == 1, 1].mean()), 1),
            "elevacion_media_ausencias": round(float(X[y == 0, 1].mean()), 1),
        }
        return res, X, y, pts

    libre, _, _, _ = assess(None)
    ajustada, X, y, pts = assess(band)
    report = {
        "descartados": skipped, "variables": ["pendiente_deg", "elevacion_m"], "bloques": f"{blocks}x{blocks}",
        "ausencias_libres": libre,
        "ausencias_mismo_rango_elevacion": {**ajustada, "rango_elevacion_m": [round(band[0]), round(band[1])]},
        "conclusion_automatica": _conclusion(libre, ajustada),
        "interpretacion_auc": "0,5 = azar; 0,7–0,8 aceptable; > 0,8 bueno (referencia común, no un umbral oficial).",
        "advertencias": [
            "Las ausencias son pseudo-ausencias: el inventario es incompleto (sin evento inventariado ≠ sin peligro).",
            "El inventario se concentra donde hay población y vías: la elevación puede reflejar ese sesgo de "
            "muestreo y no el peligro físico. Por eso se informa también la variante con ausencias en el mismo "
            "rango de elevación que los eventos.",
            "Solo dos variables (pendiente y elevación): faltan litología, geomorfología, lluvia y cobertura.",
            "La validación aleatoria se muestra solo como referencia: sobrestima por autocorrelación espacial.",
            "Un buen AUC no autoriza decisiones: la validación final la decide un experto/administrador.",
        ],
    }
    return report, X, y, pts   # el dataset exportado usa la variante con sesgo de elevación corregido


def _d(v) -> str:
    """Número con coma decimal (convención del proyecto en textos para personas)."""
    return f"{float(v):.2f}".replace(".", ",")


def _conclusion(libre: dict, ajustada: dict) -> list[str]:
    out = []
    h = libre["auc_heuristico_pendiente"]
    if h < 0.6:
        out.append(f"El índice heurístico por pendiente NO discrimina los eventos inventariados (AUC {_d(h)}): no debe "
                   "usarse como indicador de susceptibilidad en esta área.")
    e_libre, e_aj = libre["auc_solo_elevacion_baja"], ajustada["auc_solo_elevacion_baja"]
    m_libre = libre["regresion_logistica"]["espacial"]["auc_mean"]
    m_aj = ajustada["regresion_logistica"]["espacial"]["auc_mean"]
    if e_libre >= 0.7 and m_aj is not None and m_libre is not None and m_aj < m_libre - 0.05:
        out.append(f"El buen resultado con ausencias libres (AUC espacial {_d(m_libre)}) depende sobre todo de la "
                   f"elevación (AUC solo elevación {_d(e_libre)}); al corregir ese sesgo baja a {_d(m_aj)}: es probable que "
                   "refleje dónde se hizo el inventario más que el peligro físico.")
    if m_aj is not None and e_aj >= m_aj - 0.05:
        out.append(f"Incluso con el sesgo corregido, el modelo (AUC {_d(m_aj)}) apenas supera a la elevación sola "
                   f"(AUC {_d(e_aj)}): la pendiente casi no aporta información con estos datos.")
    if m_aj is not None and m_aj < 0.65:
        out.append("Con pendiente y elevación no se obtiene un modelo de susceptibilidad útil: hacen falta más "
                   "variables (litología, geomorfología, lluvia, cobertura).")
    return out or ["Sin conclusiones automáticas: revisar las métricas con criterio experto."]


def dataset_csv(X: np.ndarray, y: np.ndarray, pts: np.ndarray, bbox, arr: np.ndarray) -> bytes:
    """CSV para NEUROTRAINING (lat, lon, pendiente, elevación, evento)."""
    dlon, dlat = demlib.cell_size(bbox, arr)
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["latitud", "longitud", "pendiente_deg", "elevacion_m", "evento"])
    for (r, c), (s, e), lab in zip(pts, X, y):
        wr.writerow([round(bbox[3] - (r + 0.5) * dlat, 6), round(bbox[0] + (c + 0.5) * dlon, 6),
                     round(float(s), 3), round(float(e), 1), int(lab)])
    return buf.getvalue().encode("utf-8")


def load_fc(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
