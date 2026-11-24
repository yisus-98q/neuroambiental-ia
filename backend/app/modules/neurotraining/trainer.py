"""NEUROTRAINING: entrenamiento ligero con scikit-learn sobre CSV registrados en NEURODATA.

Principios:
- Solo algoritmos pequeños, n_jobs=1 (equipos de 4 GB).
- Siempre hay datos de prueba separados; las métricas se calculan solo sobre ellos.
- Un modelo entrenado con datos simulados queda marcado y NUNCA puede pasar a «validado».
- Los artefactos se guardan con su SHA-256 y se verifica antes de cargarlos (evita cargar
  archivos alterados: joblib/pickle puede ejecutar código).
"""
from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.neurodata.validators import read_csv_rows

MAX_FEATURES = 30
MIN_ROWS = 60          # con 25 % de prueba quedan ≥15 filas para evaluar
SMALL_TEST_WARNING = 50
# Fábricas con semilla explícita (reproducibilidad). Los hilos salen del perfil de hardware.
def _nj() -> int:
    from app.core import hardware
    return hardware.detect_profile().n_jobs


ALGORITHMS = {
    "clasificacion": {
        "random_forest": lambda s: RandomForestClassifier(n_estimators=100, max_depth=12, n_jobs=_nj(), random_state=s),
        "regresion_logistica": lambda s: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "hist_gradient_boosting": lambda s: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1,
                                                                           random_state=s),
        "mlp": lambda s: make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=500,
                                                                       early_stopping=True, random_state=s)),
    },
    "regresion": {
        "random_forest": lambda s: RandomForestRegressor(n_estimators=100, max_depth=12, n_jobs=_nj(), random_state=s),
        "ridge": lambda s: make_pipeline(StandardScaler(), Ridge()),
        "hist_gradient_boosting": lambda s: HistGradientBoostingRegressor(max_iter=200, learning_rate=0.1,
                                                                          random_state=s),
        "mlp": lambda s: make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=500,
                                                                      early_stopping=True, random_state=s)),
    },
}
# Filas mínimas por algoritmo: no se usan modelos de más capacidad de la que los datos justifican.
MIN_ROWS_BY_ALGORITHM = {"hist_gradient_boosting": 200, "mlp": 1000}
SPLITS = ("aleatorio", "espacial")


class TrainingError(ValueError):
    pass


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    features: list[str]
    target: str
    dropped_rows: int
    classes: list[str] | None
    geo_columns: list[str] = field(default_factory=list)   # columnas de coordenadas presentes en el CSV
    coords: np.ndarray | None = None                         # (lat, lon) por fila, si el CSV los tiene


# Nombres habituales de columnas de coordenadas (en minúsculas, sin tildes).
GEO_NAMES = {"lat", "latitud", "latitude", "lon", "lng", "long", "longitud", "longitude", "x", "y", "este", "norte",
             "easting", "northing", "utm_x", "utm_y", "coord_x", "coord_y"}
GEO_NOTE = ("El conjunto tiene coordenadas: los datos espaciales están autocorrelacionados y un corte aleatorio "
            "sobrestima el rendimiento. Estas métricas NO sirven para validar el modelo; se necesita una "
            "validación espacial con datos de prueba independientes (otra zona).")


def geo_columns(headers: list[str]) -> list[str]:
    return [h for h in headers if h.strip().lower().replace("í", "i") in GEO_NAMES]


_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+$")


def _to_float(v) -> float:
    s = str(v).strip()
    if _THOUSANDS.match(s):
        return math.nan  # «1,234» es ambiguo (¿miles o decimal?): la fila se descarta en lugar de adivinar
    try:
        f = float(s.replace(",", "."))
    except (TypeError, ValueError):
        return math.nan
    return f if math.isfinite(f) else math.nan


def load_dataset(raw: bytes, *, target: str, features: list[str], task: str) -> Dataset:
    headers, rows = read_csv_rows(raw)
    if target not in headers:
        raise TrainingError(f"La columna objetivo '{target}' no existe en el CSV.")
    missing = [f for f in features if f not in headers]
    if missing:
        raise TrainingError(f"Columnas inexistentes: {missing}")
    if not features or len(features) > MAX_FEATURES:
        raise TrainingError(f"Indique entre 1 y {MAX_FEATURES} columnas de entrada.")
    if target in features:
        raise TrainingError("La columna objetivo no puede ser también una entrada (fuga de datos).")
    lat_col = next((h for h in headers if h.strip().lower() in ("lat", "latitud", "latitude")), None)
    lon_col = next((h for h in headers if h.strip().lower() in ("lon", "lng", "longitud", "longitude")), None)
    X, y, dropped, coords = [], [], 0, []
    for row in rows:
        xs = [_to_float(row.get(f)) for f in features]
        t = (row.get(target) or "").strip()
        if any(math.isnan(v) for v in xs) or t == "":
            dropped += 1
            continue
        if task == "regresion":
            tv = _to_float(t)
            if math.isnan(tv):
                dropped += 1
                continue
            y.append(tv)
        else:
            y.append(t)
        X.append(xs)
        if lat_col and lon_col:
            coords.append((_to_float(row.get(lat_col)), _to_float(row.get(lon_col))))
    if len(X) < MIN_ROWS:
        raise TrainingError(f"Se necesitan al menos {MIN_ROWS} filas completas (hay {len(X)}).")
    classes = None
    if task == "clasificacion":
        classes = sorted(set(y))
        if len(classes) < 2:
            raise TrainingError("La columna objetivo necesita al menos 2 clases.")
        if len(classes) > 20:
            raise TrainingError("Demasiadas clases (>20) para una clasificación ligera.")
        counts = {c: y.count(c) for c in classes}
        rare = sorted(c for c, n in counts.items() if n < 2)
        if rare:
            raise TrainingError(f"Cada clase necesita al menos 2 filas para separar entrenamiento y prueba: {rare}")
        if round(len(y) * 0.25) < len(classes):
            raise TrainingError("Hay demasiadas clases para el número de filas: la prueba no podría incluirlas todas.")
    c = np.asarray(coords, dtype="float64") if coords else None
    if c is not None and not np.isfinite(c).all():
        c = None
    return Dataset(np.asarray(X, dtype="float64"), np.asarray(y), features, target, dropped, classes,
                   geo_columns(headers), c)


def train(ds: Dataset, *, task: str, algorithm: str, test_size: float = 0.25, seed: int = 42,
          split: str = "aleatorio", blocks: int = 4):
    try:
        factory = ALGORITHMS[task][algorithm]
    except KeyError as exc:
        raise TrainingError(f"Combinación no soportada: {task}/{algorithm}") from exc
    need = MIN_ROWS_BY_ALGORITHM.get(algorithm, MIN_ROWS)
    if len(ds.y) < need:
        raise TrainingError(f"«{algorithm}» necesita al menos {need} filas para justificar su capacidad "
                            f"(hay {len(ds.y)}): use regresión logística, ridge o random forest.")
    if algorithm == "mlp":
        from app.core import hardware
        if not hardware.detect_profile().training_allowed:
            raise TrainingError("El perfil «ligero» no entrena redes neuronales: hágalo en el equipo principal.")
    if split not in SPLITS:
        raise TrainingError(f"División desconocida: {split}")
    if split == "espacial" and ds.coords is None:
        raise TrainingError("La división espacial necesita columnas de latitud y longitud válidas en el CSV.")
    try:
        return _train(ds, lambda: factory(seed), task, test_size, seed, split, blocks, algorithm)
    except (ValueError, IndexError) as exc:  # casos borde de scikit-learn → error claro (422), no 500
        raise TrainingError(f"No se pudo entrenar/evaluar con estos datos: {exc}") from exc


def spatial_blocks(coords: np.ndarray, blocks: int) -> np.ndarray:
    """Bloque por cuantiles de latitud y longitud (rejilla blocks×blocks)."""
    qa = np.quantile(coords[:, 0], np.linspace(0, 1, blocks + 1)[1:-1])
    qo = np.quantile(coords[:, 1], np.linspace(0, 1, blocks + 1)[1:-1])
    return np.searchsorted(qa, coords[:, 0]) * blocks + np.searchsorted(qo, coords[:, 1])


def _train(ds: Dataset, factory, task: str, test_size: float, seed: int = 42, split: str = "aleatorio",
           blocks: int = 4, algorithm: str = ""):
    if split == "espacial":
        groups = spatial_blocks(ds.coords, blocks)
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        tr, te = next(gss.split(ds.X, ds.y, groups))
        X_tr, X_te, y_tr, y_te = ds.X[tr], ds.X[te], ds.y[tr], ds.y[te]
        if task == "clasificacion" and (len(set(y_te)) < 2 or len(set(y_tr)) < 2):
            raise TrainingError("Los bloques de prueba no contienen todas las clases: pruebe otra semilla o menos bloques.")
        evaluated = (f"bloques geográficos completos reservados ({blocks}×{blocks} por cuantiles de lat/lon; "
                     f"≈{int(test_size * 100)} %); NO es una región independiente")
    else:
        stratify = ds.y if task == "clasificacion" else None  # load_dataset garantiza ≥2 filas por clase
        X_tr, X_te, y_tr, y_te = train_test_split(ds.X, ds.y, test_size=test_size, random_state=seed,
                                                  stratify=stratify)
        evaluated = "25 % de filas reservadas del mismo CSV (corte aleatorio; no es un conjunto independiente)"
    model = factory()
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    import platform

    import sklearn
    metrics: dict = {
        "n_train": int(len(y_tr)), "n_test": int(len(y_te)), "dropped_rows": ds.dropped_rows,
        # Honestidad: nunca es un conjunto independiente; se dice cuál fue.
        "evaluated_on": evaluated, "division": split, "semilla": seed,
        "hiperparametros": _params(model),
        "versiones": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                      "numpy": np.__version__},
        "warnings": [],
    }
    if algorithm == "mlp":
        metrics["warnings"].append("Red neuronal (MLP): con pocos datos suele igualar o empeorar a modelos simples; "
                                   "compárela siempre con la regresión logística en los mismos datos.")
    if ds.geo_columns:
        metrics["geoespacial"] = True
        metrics["random_split_insufficient"] = True
        metrics["warnings"].append(GEO_NOTE)
        coord_feats = [f for f in ds.features if f in ds.geo_columns]
        if coord_feats:
            metrics["coordinate_features"] = coord_feats
            metrics["warnings"].append(f"Usa coordenadas como variables ({', '.join(coord_feats)}): el modelo puede "
                                       "memorizar la ubicación de los ejemplos en lugar de aprender del ambiente; "
                                       "no generalizará a otras zonas.")
    if len(y_te) < SMALL_TEST_WARNING:
        metrics["warnings"].append(f"Solo {len(y_te)} filas de prueba: las métricas son muy inciertas.")
    metrics["warnings"].append("Si los datos tienen autocorrelación espacial o temporal, un corte aleatorio "
                               "sobrestima el rendimiento; la validación requiere datos externos.")
    r4 = lambda v: round(float(v), 4)  # noqa: E731
    if task == "clasificacion":
        labels = list(model.classes_)
        metrics["accuracy"] = r4(accuracy_score(y_te, pred))
        metrics["precision_macro"] = r4(precision_score(y_te, pred, average="macro", zero_division=0))
        metrics["recall_macro"] = r4(recall_score(y_te, pred, average="macro", zero_division=0))
        metrics["f1_macro"] = r4(f1_score(y_te, pred, average="macro", zero_division=0))
        cm = confusion_matrix(y_te, pred, labels=labels)
        metrics["confusion_matrix"] = {"labels": [str(x) for x in labels], "matrix": cm.tolist()}
        # Por clase: falsos positivos y falsos negativos (la accuracy sola no basta para riesgos).
        metrics["per_class"] = {str(lbl): {"false_positives": int(cm[:, i].sum() - cm[i, i]),
                                           "false_negatives": int(cm[i, :].sum() - cm[i, i]),
                                           "support": int(cm[i, :].sum())} for i, lbl in enumerate(labels)}
        _, counts = np.unique(y_te, return_counts=True)
        metrics["baseline_majority"] = r4(counts.max() / counts.sum())
        if len(labels) == 2 and hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_te)[:, 1]
            positive = labels[1]
            metrics["positive_class"] = str(positive)
            metrics["roc_auc"] = r4(roc_auc_score(y_te == positive, proba))
            metrics["brier_score"] = r4(brier_score_loss(y_te == positive, proba))  # calibración: menor es mejor
    else:
        metrics["mae"] = r4(mean_absolute_error(y_te, pred))
        metrics["rmse"] = r4(math.sqrt(mean_squared_error(y_te, pred)))
        metrics["r2"] = r4(r2_score(y_te, pred))
        metrics["baseline_mae_mean"] = r4(np.mean(np.abs(y_te - np.mean(y_tr))))
    importances = getattr(model, "feature_importances_", None)
    if importances is not None:
        metrics["feature_importance"] = {f: round(float(v), 4) for f, v in zip(ds.features, importances)}
    return model, metrics


def _params(model) -> dict:
    """Hiperparámetros serializables (para registrar y reproducir)."""
    out = {}
    for k, v in model.get_params(deep=True).items():
        if isinstance(v, (int, float, str, bool, type(None))):
            out[k] = v
        elif isinstance(v, (tuple, list)) and all(isinstance(x, (int, float, str)) for x in v):
            out[k] = list(v)
    return out


def save_artifact(model, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path, compress=3)
    return sha256_file(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_artifact(path: Path, expected_sha256: str, root: Path):
    """Carga un artefacto propio: la ruta debe estar dentro de `root` y los bytes se leen UNA vez,
    se verifican y se cargan desde memoria (sin ventana entre verificar y cargar)."""
    resolved, base = path.resolve(), root.resolve()
    if base not in resolved.parents:
        raise TrainingError("Ruta de artefacto fuera de la carpeta de datos.")
    if not resolved.is_file():
        raise TrainingError("El artefacto del modelo no existe.")
    data = resolved.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise TrainingError("El artefacto del modelo fue modificado (SHA-256 distinto). No se carga por seguridad.")
    return joblib.load(io.BytesIO(data))


def predict_rows(model, raw: bytes, features: list[str], task: str, limit: int = 5000) -> tuple[list[dict], int]:
    headers, rows = read_csv_rows(raw)
    missing = [f for f in features if f not in headers]
    if missing:
        raise TrainingError(f"El CSV de entrada no tiene las columnas del modelo: {missing}")
    out, skipped = [], 0
    batch_idx, batch_X = [], []
    for i, row in enumerate(rows[:limit]):
        xs = [_to_float(row.get(f)) for f in features]
        if any(math.isnan(v) for v in xs):
            skipped += 1
            continue
        batch_idx.append(i)
        batch_X.append(xs)
    if not batch_X:
        return [], skipped
    X = np.asarray(batch_X, dtype="float64")
    preds = model.predict(X)
    proba = model.predict_proba(X).max(axis=1) if task == "clasificacion" and hasattr(model, "predict_proba") else None
    for k, i in enumerate(batch_idx):
        item = {"row": i, "prediction": preds[k].item() if hasattr(preds[k], "item") else preds[k]}
        if proba is not None:
            # Probabilidad que asigna el modelo a su clase predicha: NO está calibrada.
            item["model_probability"] = round(float(proba[k]), 4)
        out.append(item)
    return out, skipped
