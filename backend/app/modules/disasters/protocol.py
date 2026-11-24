"""Protocolo de validación espacial (informe de fortalecimiento científico, §6).

- Validación cruzada por bloques con ZONA DE EXCLUSIÓN: se quitan del entrenamiento los puntos a menos de
  `buffer_m` de cualquier punto de prueba (evita la fuga por vecindad en los bordes de los bloques).
- Predicciones fuera de pliegue (OOF): todas las métricas se calculan sobre puntos que el modelo no vio.
- Umbral de clasificación elegido SOLO con los datos de entrenamiento de cada pliegue (Youden), nunca con la prueba.
- Intervalo de confianza del AUC por bootstrap de BLOQUES (no de puntos, que estarían autocorrelacionados).
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

N_BOOTSTRAP = 200


def fast_auc(y: np.ndarray, p: np.ndarray) -> float:
    """AUC exacto por rangos (Mann-Whitney, con empates promediados). Equivale a roc_auc_score, pero sin su
    sobrecarga de validación (≈12 ms por llamada), que hacía inviable el bootstrap en un equipo de 4 GB."""
    n1 = int(y.sum())
    n0 = len(y) - n1
    r = rankdata(p)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _youden_threshold(y: np.ndarray, p: np.ndarray) -> float:
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[int(np.argmax(tpr - fpr))])


def spatial_oof(model_factory, X: np.ndarray, y: np.ndarray, groups: np.ndarray, xy_m: np.ndarray,
                splitter, buffer_m: float) -> dict:
    """Probabilidades fuera de pliegue con zona de exclusión, umbral por pliegue y AUC por pliegue."""
    oof = np.full(len(y), np.nan)
    pred = np.zeros(len(y), dtype=int)
    folds, removed = [], 0
    for tr, te in splitter.split(X, y, groups):
        if buffer_m > 0:
            dist, _ = cKDTree(xy_m[te]).query(xy_m[tr], k=1)
            keep = dist >= buffer_m
            removed += int((~keep).sum())
            tr = tr[keep]
        if len(set(y[tr])) < 2:
            continue
        m = model_factory()
        m.fit(X[tr], y[tr])
        thr = _youden_threshold(y[tr], m.predict_proba(X[tr])[:, 1])
        p = m.predict_proba(X[te])[:, 1]
        oof[te], pred[te] = p, (p >= thr).astype(int)
        if len(set(y[te])) == 2:
            folds.append({"auc": round(float(roc_auc_score(y[te], p)), 4), "n_eventos": int(y[te].sum()),
                          "n_ausencias": int(len(te) - y[te].sum())})
    return {"oof": oof, "pred": pred, "folds": folds, "removed_by_buffer": removed}


def block_bootstrap_auc(y: np.ndarray, p: np.ndarray, groups: np.ndarray, seed: int) -> list[float] | None:
    ok = np.isfinite(p)
    y, p, groups = y[ok], p[ok], groups[ok]
    ids = np.unique(groups)
    if len(ids) < 3:
        return None
    by = {g: np.flatnonzero(groups == g) for g in ids}
    rng = np.random.default_rng(seed)
    aucs = []
    for _ in range(N_BOOTSTRAP):
        idx = np.concatenate([by[g] for g in rng.choice(ids, size=len(ids), replace=True)])
        yi = y[idx]
        if 0 < yi.sum() < len(yi):
            aucs.append(fast_auc(yi, p[idx]))
    if len(aucs) < N_BOOTSTRAP // 2:
        return None
    return [round(float(np.percentile(aucs, 2.5)), 4), round(float(np.percentile(aucs, 97.5)), 4)]


def summarize(res: dict, y: np.ndarray, groups: np.ndarray, seed: int) -> dict:
    p, pred = res["oof"], res["pred"]
    ok = np.isfinite(p)
    yy, pp, pr = y[ok], p[ok], pred[ok]
    if len(set(yy)) < 2:
        return {"auc_mean": None, "auc_sd": None, "folds": 0}
    tp = int(((pr == 1) & (yy == 1)).sum())
    fp = int(((pr == 1) & (yy == 0)).sum())
    fn = int(((pr == 0) & (yy == 1)).sum())
    tn = int(((pr == 0) & (yy == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    fold_aucs = [f["auc"] for f in res["folds"]]
    r4 = lambda v: round(float(v), 4)  # noqa: E731
    return {
        "auc_mean": r4(np.mean(fold_aucs)) if fold_aucs else None,
        "auc_sd": r4(np.std(fold_aucs)) if fold_aucs else None,
        "folds": len(fold_aucs),
        "por_pliegue": res["folds"],
        "auc_agrupado": r4(roc_auc_score(yy, pp)),
        "auc_ic95_bloques": block_bootstrap_auc(y, p, groups, seed),
        "pr_auc": r4(average_precision_score(yy, pp)),
        "pr_auc_azar": r4(yy.mean()),
        "brier": r4(brier_score_loss(yy, pp)),
        "confusion": {"vp": tp, "fp": fp, "fn": fn, "vn": tn},
        "precision": r4(prec), "recall": r4(rec), "f1": r4(2 * prec * rec / (prec + rec) if prec + rec else 0.0),
        "excluidos_por_zona_de_exclusion": res["removed_by_buffer"],
        "umbral": "Youden, elegido con el entrenamiento de cada pliegue",
    }
