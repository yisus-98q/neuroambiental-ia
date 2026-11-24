"""Validación de la susceptibilidad con el inventario REAL de INGEMMET (protocolo del informe científico, §6).

1. Presencias: eventos del inventario dentro del DEM (una celda por evento). Se evalúan TODOS juntos y, además,
   POR TIPO DE PROCESO (código TIP_PELIGRO con ≥ `min_por_proceso` eventos): mezclar caídas y flujos anula la
   señal de la pendiente. El significado de cada código NO está confirmado por INGEMMET.
2. Pseudo-ausencias: celdas aleatorias a ≥ `min_dist_m` de todo evento («sin evento inventariado» ≠ «sin
   peligro»). Dos variantes: libres y en la misma franja de altura que los eventos (sesgo de muestreo). Se
   repiten con `n_semillas` sorteos y se informa la dispersión.
3. Variables: pendiente (°) y elevación (m) del DEM. El índice heurístico (pendiente/45°) se evalúa sin entrenar.
4. Validación cruzada espacial por bloques con zona de exclusión, métricas fuera de pliegue (AUC por pliegue,
   AUC agrupado con IC95 por bootstrap de bloques, PR-AUC, Brier, matriz de confusión con umbral elegido en
   entrenamiento). La validación aleatoria se muestra solo como referencia de cuánto infla.
Limitaciones conocidas: tamaño de bloque fijo (no derivado de un variograma); sin máscara de hielo/agua;
sin prueba independiente fuera del recorte. Nada aquí declara un modelo «validado».
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

from app.core import hardware, jobs
from app.modules.disasters import geology, protocol, terrain_vars
from app.modules.neuro3d import dem as demlib

MASS_MOVEMENT_KEYWORDS = ("desliz", "derrumbe", "caida", "caída", "huayco", "huaico", "flujo", "avalancha",
                          "reptac", "movimiento", "vuelco", "alud")
HEURISTIC_SATURATION_DEG = 45.0
_PROF = hardware.detect_profile()
MIN_EVENTS = 20
CODE_NOTE = ("Interpretación NO confirmada por INGEMMET (pendiente su diccionario oficial); el patrón de pendientes "
             "es coherente con 1100 = caídas, 1300 = deslizamientos, 1500 = flujos/huaycos.")


class ValidationError(ValueError):
    pass


def _is_mass_movement(props: dict) -> bool:
    """INGEMMET codifica el tipo (p. ej. «1000|1300»); el grupo 1000 se trata como movimientos en masa
    (correspondencia a confirmar con INGEMMET). También se aceptan descripciones en texto."""
    code = str(props.get("TIP_PELIGRO") or "")
    if code.split("|")[0] == "1000":
        return True
    text = f"{code} {props.get('NOM_PELIGRO') or ''}".lower()
    return any(k in text for k in MASS_MOVEMENT_KEYWORDS)


def event_cells(fc: dict, arr: np.ndarray, bbox, only_mass_movement: bool = True,
                code: str | None = None) -> tuple[np.ndarray, dict]:
    h, w = arr.shape
    dlon, dlat = demlib.cell_size(bbox, arr)
    cells, skipped = set(), {"fuera_del_dem": 0, "otro_tipo": 0, "sin_dato": 0}
    for f in fc.get("features", []):
        g, props = f.get("geometry") or {}, f.get("properties") or {}
        if g.get("type") != "Point":
            continue
        if code is not None and str(props.get("TIP_PELIGRO") or "") != code:
            continue
        if only_mass_movement and not _is_mass_movement(props):
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
    if len(presences) < MIN_EVENTS:
        raise ValidationError(f"Muy pocos eventos útiles dentro del DEM ({len(presences)}; mínimo {MIN_EVENTS}).")
    mask = np.zeros(arr.shape, dtype=bool)
    mask[presences[:, 0], presences[:, 1]] = True
    dx = float(np.mean(demlib._spacing(bbox, arr)[0]))
    dist_cells = ndimage.distance_transform_edt(~mask)
    eligible = np.isfinite(arr) & (dist_cells * dx >= min_dist_m)
    if elevation_range is not None:
        with np.errstate(invalid="ignore"):
            eligible &= (arr >= elevation_range[0]) & (arr <= elevation_range[1])
    cand = np.argwhere(eligible)
    n_abs = min(len(cand), ratio * len(presences))
    if n_abs < len(presences):
        raise ValidationError("No hay suficientes celdas lejos de los eventos para generar ausencias.")
    rng = np.random.default_rng(seed)
    absences = cand[rng.choice(len(cand), size=n_abs, replace=False)]
    return np.vstack([presences, absences]), np.r_[np.ones(len(presences), int), np.zeros(n_abs, int)]


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


def _models(seed: int, n_topo: int = 2, geo: bool = False, n_cont: int | None = None) -> dict:
    """(fábrica, columnas). «base» = solo pendiente y elevación; «regresion_logistica» = toda la topografía;
    «regresion_logistica_geo» = topografía + clases geológicas (si se pidieron)."""
    lr = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))  # noqa: E731
    out = {
        "regresion_logistica": (lr, list(range(n_topo))),
        "regresion_logistica_base": (lr, [0, 1]),
        "bosque_aleatorio": (lambda: RandomForestClassifier(n_estimators=_PROF.rf_trees, max_depth=6,
                                                            min_samples_leaf=5, n_jobs=_PROF.n_jobs,
                                                            random_state=seed), None),
    }
    if n_cont and n_cont > n_topo:
        out["regresion_logistica_ndvi"] = (lr, list(range(n_cont)))   # topografía + capas continuas extra
    if geo:
        out["regresion_logistica_geo"] = (lr, None)
    return out


CHEAP = ("regresion_logistica", "regresion_logistica_base", "regresion_logistica_geo", "regresion_logistica_ndvi")


def _onehot(cats: dict, pts: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Columnas 0/1 de las clases geológicas conservadas (la clase de referencia es «otras»)."""
    cols, names = [], []
    for kind, (idx, cnames, keep) in cats.items():
        codes = idx[pts[:, 0], pts[:, 1]]
        for k in keep:
            cols.append((codes == k).astype("float64"))
            names.append(f"{kind}={cnames[k]}")
    return (np.column_stack(cols) if cols else np.empty((len(pts), 0))), names


def _variant(arr, bbox, stack, presences, xy_scale, *, ratio, min_dist_m, blocks, seed, n_seeds, buffer_m,
             elevation_range, cats=None, extras=None):
    """Una variante de pseudo-ausencias evaluada con n_seeds sorteos; métricas completas del primero.
    Todos los modelos de un sorteo usan los MISMOS puntos (las filas sin dato se quitan para todos)."""
    cont = {**stack, **(extras or {})}
    n_topo, n_cont, geo = len(stack), len(cont), bool(cats)
    seeds_auc: dict[str, list[float]] = {k: [] for k in _models(seed, n_topo, geo, n_cont)}
    first = None
    for s in range(n_seeds):
        jobs.check_cancel()
        pts, y = build_points(arr, bbox, presences, ratio, min_dist_m, seed + s, elevation_range)
        names = list(cont)
        X = np.column_stack([cont[n][pts[:, 0], pts[:, 1]] for n in names]).astype("float64")
        if geo:
            X = np.column_stack([X, _onehot(cats, pts)[0]])
        ok = np.isfinite(X).all(axis=1)
        dropped = {"eventos": int((~ok & (y == 1)).sum()), "ausencias": int((~ok & (y == 0)).sum())}
        X, y, pts = X[ok], y[ok], pts[ok]
        groups = spatial_groups(pts, arr.shape, blocks)
        k = min(5, len(set(groups.tolist())))
        if k < 3:
            raise ValidationError("El área es demasiado pequeña para una validación espacial por bloques.")
        xy_m = np.c_[pts[:, 1] * xy_scale[0], pts[:, 0] * xy_scale[1]]
        detail = {}
        # El bosque aleatorio es caro en un equipo de 4 GB: se evalúa con el primer sorteo; la variación entre
        # sorteos de ausencias se mide con la regresión logística (modelo de referencia).
        models = {n: m for n, m in _models(seed, n_topo, geo, n_cont).items() if s == 0 or n in CHEAP}
        for name, (factory, cols) in models.items():
            Xm = X if cols is None else X[:, cols]
            res = protocol.spatial_oof(factory, Xm, y, groups, xy_m, GroupKFold(n_splits=k), buffer_m)
            summ = protocol.summarize(res, y, groups, seed)
            if summ["auc_mean"] is not None:
                seeds_auc[name].append(summ["auc_mean"])
            detail[name] = summ
        if first is None:
            rand = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
            first = {
                "n_presencias": int(y.sum()), "n_ausencias": int(len(y) - y.sum()), "folds_espaciales": k,
                "auc_heuristico_pendiente": round(float(roc_auc_score(
                    y, np.clip(X[:, 0] / HEURISTIC_SATURATION_DEG, 0, 1))), 4),
                "auc_solo_elevacion_baja": round(float(roc_auc_score(y, -X[:, 1])), 4),
                "pendiente_media_eventos": round(float(X[y == 1, 0].mean()), 2),
                "pendiente_media_ausencias": round(float(X[y == 0, 0].mean()), 2),
                "elevacion_media_eventos": round(float(X[y == 1, 1].mean()), 1),
                "elevacion_media_ausencias": round(float(X[y == 0, 1].mean()), 1),
                "por_variable": _univariate(X[:, :n_cont], y, names),
                "puntos_sin_dato_descartados": dropped,
            }
            lr = _models(seed)["regresion_logistica"][0]
            first["regresion_logistica"] = {"espacial": detail["regresion_logistica"],
                                            "aleatoria_referencia": _cv_auc(lr, X[:, :n_topo], y, rand)}
            if geo:
                first["regresion_logistica_geo"] = {"espacial": detail["regresion_logistica_geo"]}
            first["regresion_logistica_base"] = {"espacial": detail["regresion_logistica_base"]}
            if "regresion_logistica_ndvi" in detail:
                first["regresion_logistica_ndvi"] = {"espacial": detail["regresion_logistica_ndvi"]}
            # Referencia aleatoria solo con el modelo lineal: basta para mostrar cuánto infla (ahorra memoria/tiempo).
            first["bosque_aleatorio"] = {"espacial": detail["bosque_aleatorio"],
                                         "aleatoria_referencia": {"auc_mean": None, "auc_sd": None, "folds": 0}}
            data = (X, y, pts)
    for name, vals in seeds_auc.items():
        first[name]["espacial"]["auc_semillas"] = {
            "media": round(float(np.mean(vals)), 4) if vals else None,
            "sd": round(float(np.std(vals)), 4) if vals else None, "n": len(vals)}
    if elevation_range is not None:
        first["rango_elevacion_m"] = [round(elevation_range[0]), round(elevation_range[1])]
    return first, data


def _univariate(X: np.ndarray, y: np.ndarray, names: list[str]) -> dict:
    """AUC de cada variable sola (sin entrenar) y su dirección: qué distingue a los eventos."""
    out = {}
    for i, n in enumerate(names):
        a = float(roc_auc_score(y, X[:, i]))
        out[n] = {"auc": round(a, 4), "auc_discriminante": round(max(a, 1 - a), 4),
                  "direccion": "mayor en eventos" if a >= 0.5 else "menor en eventos",
                  "mediana_eventos": round(float(np.median(X[y == 1, i])), 2),
                  "mediana_ausencias": round(float(np.median(X[y == 0, i])), 2)}
    return out


def _assess(arr, bbox, stack, presences, xy_scale, cats=None, **kw):
    ev_elev = arr[presences[:, 0], presences[:, 1]]
    band = (float(np.percentile(ev_elev, 5)), float(np.percentile(ev_elev, 95)))
    libre, _ = _variant(arr, bbox, stack, presences, xy_scale, elevation_range=None, cats=cats, **kw)
    ajustada, data = _variant(arr, bbox, stack, presences, xy_scale, elevation_range=band, cats=cats, **kw)
    out = {"ausencias_libres": libre, "ausencias_mismo_rango_elevacion": ajustada,
           "conclusion_automatica": _conclusion(libre, ajustada)}
    if cats:
        out["geologia_razon_frecuencia"] = {k: geology.frequency_ratio(idx, names, presences)
                                            for k, (idx, names, _) in cats.items()}
    return out, data


def evaluate(arr: np.ndarray, bbox, fc: dict, *, ratio: int = 3, min_dist_m: float = 300.0, blocks: int = 4,
             seed: int = 42, n_seeds: int = 5, buffer_m: float = 500.0, min_por_proceso: int = 30,
             only_mass_movement: bool = True,
             categorical: dict | None = None,
             extra_layers: dict | None = None) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray]:
    """`categorical`: {capa: (índice de clase por celda, nombres)} rasterizado a la malla del DEM.
    `extra_layers`: {nombre: matriz continua en la malla del DEM} (p. ej. «ndvi_anillo»)."""
    global _PROF
    _PROF = hardware.detect_profile()
    n_seeds = max(1, min(n_seeds, _PROF.validation_seeds_max))
    presences, skipped = event_cells(fc, arr, bbox, only_mass_movement)
    if len(presences) < MIN_EVENTS:
        raise ValidationError(f"Muy pocos eventos útiles dentro del DEM ({len(presences)}; mínimo {MIN_EVENTS}).")
    stack = terrain_vars.compute(arr, bbox)
    jobs.check_cancel()
    dxs, dy = demlib._spacing(bbox, arr)
    xy_scale = (float(np.mean(dxs)), float(dy))
    vario = protocol.variogram_range(stack, xy_scale, seed)
    extent_m = min(arr.shape[1] * xy_scale[0], arr.shape[0] * xy_scale[1])
    rango_med = float(np.median([v["alcance_m"] for v in vario.values()])) if vario else None
    blocks_auto = blocks == 0
    if blocks_auto:
        blocks = int(min(8, max(3, extent_m // rango_med))) if rango_med else 4
    cats = {k: (idx, names, geology.kept_classes(idx, names)) for k, (idx, names) in (categorical or {}).items()}
    cats = {k: v for k, v in cats.items() if v[2]} or None
    kw = {"ratio": ratio, "min_dist_m": min_dist_m, "blocks": blocks, "seed": seed, "n_seeds": n_seeds,
          "buffer_m": buffer_m, "cats": cats, "extras": extra_layers or None}
    todos, (X, y, pts) = _assess(arr, bbox, stack, presences, xy_scale, **kw)

    codes: dict[str, int] = {}
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        if not only_mass_movement or _is_mass_movement(p):
            c = str(p.get("TIP_PELIGRO") or "")
            codes[c] = codes.get(c, 0) + 1
    por_proceso, omitidos = {}, {}
    for code, n in sorted(codes.items()):
        if len(codes) == 1:
            omitidos[code] = "único tipo presente: idéntico a «todos»"
            break
        cells, _ = event_cells(fc, arr, bbox, only_mass_movement, code=code)
        if len(cells) < max(min_por_proceso, MIN_EVENTS):
            omitidos[code] = len(cells)
            continue
        try:
            por_proceso[code], _ = _assess(arr, bbox, stack, cells, xy_scale, **kw)
        except ValidationError as exc:
            omitidos[code] = f"{len(cells)} ({exc})"
    block_km = [round((bbox[2] - bbox[0]) * demlib.M_PER_DEG_LON * math.cos(math.radians((bbox[1] + bbox[3]) / 2))
                      / blocks / 1000, 1), round((bbox[3] - bbox[1]) * demlib.M_PER_DEG_LAT / blocks / 1000, 1)]
    report = {
        "descartados": skipped, "variables": list(stack) + list(extra_layers or {}), "bloques": f"{blocks}x{blocks}",
        "variables_descripcion": {k: terrain_vars.DESCRIPTIONS.get(k, k) for k in [*stack, *(extra_layers or {})]},
        "geologia_clases_usadas": {k: [names[i] for i in keep] for k, (_, names, keep) in (cats or {}).items()},
        **todos,
        "por_proceso": por_proceso, "procesos_omitidos_por_pocos_eventos": omitidos, "nota_codigos": CODE_NOTE,
        "protocolo": {
            "tamano_bloque_km": block_km, "bloques_automaticos": blocks_auto,
            "variograma": {"por_variable": vario, "alcance_mediano_m": rango_med,
                           "bloque_cubre_alcance": bool(rango_med is not None
                                                         and min(block_km) * 1000 >= rango_med)},
            "zona_exclusion_m": buffer_m, "semillas_ausencias": n_seeds,
            "semilla_base": seed, "ratio_ausencias": ratio, "distancia_min_ausencias_m": min_dist_m,
            "min_eventos_por_proceso": min_por_proceso,
            "pendiente": ["sin máscara de hielo ni agua",
                          "sin prueba independiente fuera del recorte", "DEM remuestreado (no a 30 m nativos)"],
        },
        "interpretacion_auc": "0,5 = azar; 0,7–0,8 aceptable; > 0,8 bueno (referencia común, no un umbral oficial).",
        "interpretacion_metricas": {
            "pr_auc": "Depende de la proporción eventos/ausencias; compárela con su valor de azar (pr_auc_azar).",
            "brier": "Con pseudo-ausencias la escala de probabilidad es arbitraria: solo vale para comparar modelos.",
            "confusion": "Con pseudo-ausencias, un falso positivo puede ser un evento no inventariado.",
        },
        "advertencias": [
            "Las ausencias son pseudo-ausencias: el inventario es incompleto (sin evento inventariado ≠ sin peligro).",
            "El inventario se concentra donde hay población y vías: la elevación puede reflejar ese sesgo de "
            "muestreo y no el peligro físico. Por eso se informa también la variante con ausencias en el mismo "
            "rango de elevación que los eventos.",
            "Variables solo topográficas (derivadas del DEM): faltan litología, geomorfología, lluvia y cobertura.",
            "La red de cauces se deriva del DEM (no es la red oficial de la ANA) con un umbral de área fijo.",
            *(["La geomorfología puede ser circular: algunas unidades (p. ej. vertientes coluviales, abanicos) se "
               "cartografían a partir de depósitos de movimientos en masa; su aporte no prueba capacidad predictiva."]
              if cats and "geomorfologia" in cats else []),
            *(["En la litología, la clase de depósitos recientes («Sedimento») puede incluir los depósitos de los "
               "propios eventos (sobre todo flujos/huaycos): parte de su aporte puede ser circular."]
              if cats and "litologia" in cats else []),
            *(["NDVI: imagen de 2024, posterior a los eventos (158 fechados en 2007 y 23 entre 2018 y 2026). Puede "
               "reflejar la cicatriz del propio evento (fuga temporal) o la cobertura actual; no es la condición "
               "previa. Las celdas sin dato (nubes, nieve, agua) quedan fuera para TODOS los modelos."]
              if extra_layers and "ndvi_anillo" in extra_layers else []),
            *(["La razón de frecuencia geológica es descriptiva (usa todos los eventos); solo el modelo con "
               "validación espacial mide capacidad predictiva."] if cats else []),
            "La validación aleatoria se muestra solo como referencia: sobrestima por autocorrelación espacial.",
            "Un buen AUC no autoriza decisiones: la validación final la decide un experto/administrador.",
        ],
    }
    return report, X, y, pts   # el dataset exportado: todos los procesos, variante con franja de elevación


def _d(v) -> str:
    """Número con coma decimal (convención del proyecto en textos para personas)."""
    return f"{float(v):.2f}".replace(".", ",")


def _conclusion(libre: dict, ajustada: dict) -> list[str]:
    out = []
    h = libre["auc_heuristico_pendiente"]
    if h < 0.4:
        out.append(f"Relación INVERSA con la pendiente (AUC {_d(h)}): estos eventos están en terreno más llano que las "
                   "ausencias (coherente con depósitos de flujos en cauces y abanicos). El índice heurístico los "
                   "clasifica al revés.")
    elif h < 0.6:
        out.append(f"El índice heurístico por pendiente NO discrimina los eventos inventariados (AUC {_d(h)}): no debe "
                   "usarse como indicador de susceptibilidad en esta área.")
    h_aj = ajustada["auc_heuristico_pendiente"]
    if h_aj >= 0.7:
        out.append(f"Con el sesgo de altura corregido, la pendiente sola SÍ discrimina estos eventos (AUC {_d(h_aj)}, "
                   "sin entrenar): coherente con procesos de laderas empinadas. Sigue sin validar (falta una prueba "
                   "independiente fuera del recorte).")
    for name, u in (ajustada.get("por_variable") or {}).items():
        if name in ("pendiente_deg", "elevacion_m") or u["auc_discriminante"] < 0.7:
            continue
        out.append(f"Con el sesgo de altura corregido, «{name}» sola SÍ discrimina estos eventos (AUC "
                   f"{_d(u['auc_discriminante'])}, {u['direccion']}: mediana {_d(u['mediana_eventos'])} frente a "
                   f"{_d(u['mediana_ausencias'])}). Sin entrenar (solo se elige la dirección); sigue sin validar.")
    e_libre, e_aj = libre["auc_solo_elevacion_baja"], ajustada["auc_solo_elevacion_baja"]
    m_libre = libre["regresion_logistica"]["espacial"]["auc_mean"]
    m_aj = ajustada["regresion_logistica"]["espacial"]["auc_mean"]
    if e_libre >= 0.7 and m_aj is not None and m_libre is not None and m_aj < m_libre - 0.05:
        out.append(f"El buen resultado con ausencias libres (AUC espacial {_d(m_libre)}) depende sobre todo de la "
                   f"elevación (AUC solo elevación {_d(e_libre)}); al corregir ese sesgo baja a {_d(m_aj)}: es probable "
                   "que refleje dónde se hizo el inventario más que el peligro físico.")
    if m_aj is not None and e_aj >= m_aj - 0.05:
        out.append(f"Incluso con el sesgo corregido, el modelo (AUC {_d(m_aj)}) apenas supera a la elevación sola "
                   f"(AUC {_d(e_aj)}): las demás variables casi no aportan información con estos datos.")
    ic = ajustada["regresion_logistica"]["espacial"].get("auc_ic95_bloques")
    if ic and ic[0] <= 0.6:
        out.append(f"El intervalo de confianza del AUC (bloques) llega a {_d(ic[0])}: la evidencia es débil o inestable.")
    base_aj = (ajustada.get("regresion_logistica_base") or {}).get("espacial", {}).get("auc_mean")
    if base_aj is not None and m_aj is not None:
        if m_aj >= base_aj + 0.05:
            top = sorted((ajustada.get("por_variable") or {}).items(),
                         key=lambda kv: -kv[1]["auc_discriminante"])[:2]
            names = ", ".join(f"{k} ({v['direccion']}, AUC {_d(v['auc_discriminante'])})" for k, v in top)
            out.append(f"Las variables derivadas del DEM mejoran el modelo: AUC {_d(base_aj)} → {_d(m_aj)} "
                       f"(sesgo corregido). Las más discriminantes: {names}.")
        else:
            best = max((u["auc_discriminante"] for u in (ajustada.get("por_variable") or {}).values()), default=0)
            extra = (f" Una sola variable llega a AUC {_d(best)}: combinarlas con tan pocos eventos no ayuda "
                     "(variables correlacionadas o sobreajuste)." if best > m_aj + 0.02 else "")
            out.append("Las variables nuevas (curvatura, TPI, distancia a cauce) no mejoran el modelo de forma "
                       f"apreciable: AUC {_d(base_aj)} → {_d(m_aj)}.{extra}")
    ndvi_aj = (ajustada.get("regresion_logistica_ndvi") or {}).get("espacial", {}).get("auc_mean")
    if ndvi_aj is not None and m_aj is not None:
        verb = "mejora" if ndvi_aj >= m_aj + 0.05 else "no mejora de forma apreciable"
        out.append(f"Añadir el NDVI {verb} el modelo topográfico: AUC {_d(m_aj)} → {_d(ndvi_aj)} (mismos puntos, "
                   "validación espacial, sesgo de altura corregido).")
    geo_aj = (ajustada.get("regresion_logistica_geo") or {}).get("espacial", {}).get("auc_mean")
    if geo_aj is not None and m_aj is not None:
        verb = "mejora" if geo_aj >= m_aj + 0.05 else "no mejora de forma apreciable"
        out.append(f"Añadir las clases geológicas {verb} el modelo topográfico: AUC {_d(m_aj)} → {_d(geo_aj)} "
                   "(validación espacial, sesgo de altura corregido).")
    if m_aj is not None and m_aj < 0.65:
        out.append("Con pendiente y elevación no se obtiene un modelo de susceptibilidad útil: hacen falta más "
                   "variables (litología, geomorfología, lluvia, cobertura).")
    return out or ["Sin conclusiones automáticas: revisar las métricas con criterio experto."]


def dataset_csv(X: np.ndarray, y: np.ndarray, pts: np.ndarray, bbox, arr: np.ndarray,
                names: list[str] | None = None) -> bytes:
    """CSV para NEUROTRAINING (lat, lon, variables del terreno, evento)."""
    names = names or ["pendiente_deg", "elevacion_m"]
    dlon, dlat = demlib.cell_size(bbox, arr)
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["latitud", "longitud", *names, "evento"])
    for (r, c), row, lab in zip(pts, X, y):
        wr.writerow([round(bbox[3] - (r + 0.5) * dlat, 6), round(bbox[0] + (c + 0.5) * dlon, 6),
                     *[round(float(v), 3) for v in row[:len(names)]], int(lab)])
    return buf.getvalue().encode("utf-8")


def load_fc(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
