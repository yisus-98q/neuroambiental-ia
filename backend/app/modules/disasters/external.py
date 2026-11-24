"""Misión 2.1 — evaluación EXTERNA (docs/MISION_2_1_PROTOCOLO_VALIDACION_EXTERNA.md, prerregistrado).

Todo se entrena SOLO con la zona de entrenamiento (A): dirección de cada variable, coeficientes, clases de
litología conservadas y umbral de Youden. La zona externa (B) solo aporta puntos de evaluación: sus etiquetas no
ajustan nada. Métricas en B: AUC con IC 95 % por bootstrap de bloques 3×3, PR-AUC, Brier, calibración en 5 tramos,
matriz de confusión con el umbral de A, precisión, sensibilidad, especificidad y F1; 10 sorteos de ausencias.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core import hardware, jobs
from app.modules.disasters import geology, protocol, terrain_vars, validation

GROUPS = ("todos", "1000|1100", "1000|1300", "1000|1500")
TOPO = ("pendiente_deg", "elevacion_m", "curvatura", "tpi_m", "dist_cauce_m")
TRAIN_SEED = 42
TEST_SEEDS = tuple(range(100, 110))
MIN_EVENTS_STATUS = 30
SEDIMENTO = "Sedimento"


def _presences(fc, arr, bbox, group):
    code = None if group == "todos" else group
    cells, _ = validation.event_cells(fc, arr, bbox, True, code=code)
    return cells


def _features(stack, lito, pts, lito_classes):
    X = np.column_stack([stack[n][pts[:, 0], pts[:, 1]] for n in TOPO]).astype("float64")
    if lito is not None:
        idx, names = lito
        codes = idx[pts[:, 0], pts[:, 1]]
        name_of = np.array(names, dtype=object)[codes]
        X = np.column_stack([X] + [(name_of == c).astype("float64") for c in lito_classes])
    return X


def _youden(y, s):
    fpr, tpr, thr = roc_curve(y, s)
    return float(thr[int(np.argmax(tpr - fpr))])


def _specs(n_lito: int, lito_classes: list[str]):
    """(nombre, columnas, tipo). Tipos: 'var' (una variable, signo de A), 'heur', 'lr', 'rf'."""
    out = [(f"V-{n}", [i], "var") for i, n in enumerate(TOPO)]
    out += [("R1-solo_elevacion", [1], "var"), ("R2-heuristico_pendiente", [0], "heur"),
            ("M1-base", [0, 1], "lr"), ("M2-topografico", list(range(5)), "lr"), ("M4-bosque", list(range(5)), "rf")]
    if n_lito:
        out.append(("M3-topo+litologia", list(range(5 + n_lito)), "lr"))
        keep = [5 + i for i, c in enumerate(lito_classes) if c != SEDIMENTO]
        out.append(("M3s-sin_Sedimento", list(range(5)) + keep, "lr"))
    return out


def train(stack_a, lito_a, arr_a, bbox_a, fc_a, group, lito_classes, ratio=3, min_dist_m=300.0):
    pres = _presences(fc_a, arr_a, bbox_a, group)
    pts, y = validation.build_points(arr_a, bbox_a, pres, ratio, min_dist_m, TRAIN_SEED, None)
    X = _features(stack_a, lito_a, pts, lito_classes)
    ok = np.isfinite(X).all(axis=1)
    X, y = X[ok], y[ok]
    prof = hardware.detect_profile()
    models = {}
    for name, cols, kind in _specs(len(lito_classes), lito_classes):
        Xc = X[:, cols]
        if kind == "var":
            sign = 1.0 if protocol.fast_auc(y, Xc[:, 0]) >= 0.5 else -1.0
            models[name] = {"kind": kind, "cols": cols, "sign": sign, "thr": _youden(y, sign * Xc[:, 0]),
                            "auc_train": round(protocol.fast_auc(y, sign * Xc[:, 0]), 4)}
        elif kind == "heur":
            s = np.clip(Xc[:, 0] / validation.HEURISTIC_SATURATION_DEG, 0, 1)
            models[name] = {"kind": kind, "cols": cols, "thr": _youden(y, s), "auc_train": round(protocol.fast_auc(y, s), 4)}
        else:
            est = (make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)) if kind == "lr" else
                   RandomForestClassifier(n_estimators=prof.rf_trees, max_depth=6, min_samples_leaf=5,
                                          n_jobs=prof.n_jobs, random_state=TRAIN_SEED))
            est.fit(Xc, y)
            p = est.predict_proba(Xc)[:, 1]
            models[name] = {"kind": kind, "cols": cols, "est": est, "thr": _youden(y, p),
                            "auc_train": round(protocol.fast_auc(y, p), 4)}
    return models, {"n_eventos": int(y.sum()), "n_ausencias": int(len(y) - y.sum())}


def _score(m, X):
    Xc = X[:, m["cols"]]
    if m["kind"] == "var":
        return m["sign"] * Xc[:, 0], False
    if m["kind"] == "heur":
        return np.clip(Xc[:, 0] / validation.HEURISTIC_SATURATION_DEG, 0, 1), False
    return m["est"].predict_proba(Xc)[:, 1], True


def _calibration(y, p, bins=5):
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    out = []
    for i in range(bins):
        sel = (p >= q[i]) & (p <= q[i + 1]) if i == bins - 1 else (p >= q[i]) & (p < q[i + 1])
        if sel.any():
            out.append({"prob_media": round(float(p[sel].mean()), 3), "tasa_observada": round(float(y[sel].mean()), 3),
                        "n": int(sel.sum())})
    return out


def _metrics(y, s, is_prob, thr, groups, seed):
    pred = (s >= thr).astype(int)
    tp, fp = int(((pred == 1) & (y == 1)).sum()), int(((pred == 1) & (y == 0)).sum())
    fn, tn = int(((pred == 0) & (y == 1)).sum()), int(((pred == 0) & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
    r4 = lambda v: None if v is None else round(float(v), 4)  # noqa: E731
    out = {"auc": r4(protocol.fast_auc(y, s)), "auc_ic95_bloques": protocol.block_bootstrap_auc(y, s, groups, seed),
           "pr_auc": r4(average_precision_score(y, s)), "pr_auc_azar": r4(y.mean()),
           "confusion": {"vp": tp, "fp": fp, "vn": tn, "fn": fn}, "precision": r4(prec), "sensibilidad": r4(rec),
           "especificidad": r4(spec), "f1": r4(f1), "umbral_fijado_en_entrenamiento": r4(thr)}
    if is_prob:
        out["brier"] = r4(brier_score_loss(y, s))
        out["calibracion"] = _calibration(y, s)
    else:
        out["brier"] = None
        out["calibracion"] = "no aplica: la puntuación no es una probabilidad"
    return out


def evaluate_zone(models, stack_b, lito_b, arr_b, bbox_b, fc_b, group, lito_classes, ratio=3, min_dist_m=300.0):
    pres = _presences(fc_b, arr_b, bbox_b, group)
    res = {"n_eventos_externos": int(len(pres))}
    if len(pres) < validation.MIN_EVENTS:
        res["no_calculado"] = f"Solo {len(pres)} eventos externos (mínimo técnico {validation.MIN_EVENTS})."
        return res
    ev_elev = arr_b[pres[:, 0], pres[:, 1]]
    band = (float(np.percentile(ev_elev, 5)), float(np.percentile(ev_elev, 95)))
    for variant, er in (("libre", None), ("franja", band)):
        per = {name: [] for name in models}
        detail = {}
        for k, sd in enumerate(TEST_SEEDS):
            jobs.check_cancel()
            pts, y = validation.build_points(arr_b, bbox_b, pres, ratio, min_dist_m, sd, er)
            X = _features(stack_b, lito_b, pts, lito_classes)
            ok = np.isfinite(X).all(axis=1)
            X, y, pts = X[ok], y[ok], pts[ok]
            groups = validation.spatial_groups(pts, arr_b.shape, 3)
            for name, m in models.items():
                s, is_prob = _score(m, X)
                per[name].append(protocol.fast_auc(y, s))
                if k == 0:
                    detail[name] = _metrics(y, s, is_prob, m["thr"], groups, sd)
        for name in models:
            detail[name]["auc_sorteos"] = {"media": round(float(np.mean(per[name])), 4),
                                           "sd": round(float(np.std(per[name])), 4), "n": len(per[name])}
        res[variant] = detail
    res["rango_elevacion_franja_m"] = [round(band[0]), round(band[1])]
    return res


def decide(group_res: dict, name: str, n_events: int) -> dict:
    """Estado según los criterios PRERREGISTRADOS (§7 del protocolo), en la variante franja."""
    f = (group_res.get("franja") or {}).get(name)
    if n_events < MIN_EVENTS_STATUS or f is None:
        return {"estado": "VALIDACIÓN INSUFICIENTE", "motivo": f"{n_events} eventos externos (< {MIN_EVENTS_STATUS})"}
    ic = f.get("auc_ic95_bloques")
    if not ic or ic[1] - ic[0] > 0.30:
        return {"estado": "VALIDACIÓN INSUFICIENTE", "motivo": f"IC 95 % no calculable o demasiado ancho ({ic})"}
    auc = f["auc_sorteos"]["media"]
    if auc < 0.60 or ic[0] < 0.50:
        return {"estado": "NO VALIDADO", "motivo": f"AUC externo {auc:.2f}, IC95 inferior {ic[0]:.2f}"}
    ref = group_res["franja"]["R1-solo_elevacion"]["auc_sorteos"]["media"]
    circ = name.startswith("M3-") and not (group_res["franja"].get("M3s-sin_Sedimento", {}).get("auc_sorteos", {})
                                          .get("media", 0) >= 0.70)
    ok = (auc >= 0.70 and ic[0] >= 0.60 and auc - ref >= 0.05 and f["auc_sorteos"]["sd"] <= 0.03 and not circ)
    if ok:
        return {"estado": "VALIDACIÓN EXTERNA PROMETEDORA",
                "motivo": f"AUC {auc:.2f}, IC95 {ic[0]:.2f}–{ic[1]:.2f}, +{auc - ref:.2f} sobre solo elevación",
                "nota": "No es «validado»: falta una segunda zona independiente y dos aprobaciones humanas."}
    return {"estado": "EXPERIMENTAL", "motivo": f"AUC {auc:.2f}, IC95 {ic[0]:.2f}–{ic[1]:.2f}, solo elevación {ref:.2f}"
            + ("; posible circularidad (depende de «Sedimento»)" if circ else "")}


def run(arr_a, bbox_a, fc_a, lito_fc_a, arr_b, bbox_b, fc_b, lito_fc_b) -> dict:
    """Ejecuta la evaluación externa completa, una zona a la vez (memoria acotada)."""
    lito_a = geology.rasterize(lito_fc_a, "TIPO_UNIDAD", arr_a, bbox_a) if lito_fc_a else None
    lito_classes = [lito_a[1][k] for k in geology.kept_classes(*lito_a)] if lito_a else []
    stack_a = terrain_vars.compute(arr_a, bbox_a)
    trained, train_info = {}, {}
    for g in GROUPS:
        jobs.check_cancel()
        try:
            trained[g], train_info[g] = train(stack_a, lito_a, arr_a, bbox_a, fc_a, g, lito_classes)
        except validation.ValidationError as exc:
            train_info[g] = {"error": str(exc)}
    del stack_a, lito_a
    lito_b = geology.rasterize(lito_fc_b, "TIPO_UNIDAD", arr_b, bbox_b) if lito_fc_b else None
    if lito_b is not None:
        b_names = set(lito_b[1])
        missing = [c for c in lito_classes if c not in b_names]
    else:
        missing = lito_classes
    stack_b = terrain_vars.compute(arr_b, bbox_b)
    out = {"grupos": {}, "clases_litologia_de_entrenamiento": lito_classes,
           "clases_ausentes_en_zona_externa": missing, "semilla_entrenamiento": TRAIN_SEED,
           "semillas_ausencias_externas": list(TEST_SEEDS)}
    for g, models in trained.items():
        res = evaluate_zone(models, stack_b, lito_b, arr_b, bbox_b, fc_b, g, lito_classes)
        res["entrenamiento"] = {**train_info[g], "auc_entrenamiento": {n: m["auc_train"] for n, m in models.items()}}
        n = res["n_eventos_externos"]
        res["estados"] = {name: decide(res, name, n) for name in models} if "franja" in res else \
            {name: {"estado": "VALIDACIÓN INSUFICIENTE", "motivo": res.get("no_calculado")} for name in models}
        out["grupos"][g] = res
    return out
