"""Capas geológicas de INGEMMET (uso INTERNO autorizado por el usuario; sin licencia abierta; no redistribuir).

- Litología: «Mapa Geológico Integrado» 1:50 000 (SERV_GEOLOGIA_50K_INTEGRADA, capa 7), campo TIPO_UNIDAD.
- Geomorfología: «Geomorfología por región» (SERV_GEOMORFOLOGIA, capa 0), campo SUBUNIDAD.
Se usan los NOMBRES OFICIALES de las clases tal como los publica el servicio, sin reinterpretarlos.
Las geometrías se simplifican en el servidor (maxAllowableOffset ≈ 20 m) para que el recorte pese poco.
Advertencia: la geomorfología puede ser circular (algunas unidades se cartografían a partir de depósitos de
movimientos en masa); se informa por separado y nunca se usa sola como prueba de un modelo.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
from rasterio import features
from rasterio.transform import from_origin
from sqlalchemy.orm import Session

from app.models import DataRecord, User
from app.modules.neuro3d import dem as demlib
from app.neurodata.service import store_file
from app.neurodata.validators import validate_geojson

HOST = "geocatmin.ingemmet.gob.pe"
BASE = f"https://{HOST}/arcgis/rest/services"
LAYERS = {
    "litologia": {"url": f"{BASE}/SERV_GEOLOGIA_50K_INTEGRADA/MapServer/7/query", "field": "TIPO_UNIDAD",
                  "name": "INGEMMET — Mapa Geológico Integrado 1:50 000 (litología, TIPO_UNIDAD)"},
    "geomorfologia": {"url": f"{BASE}/SERV_GEOMORFOLOGIA/MapServer/0/query", "field": "SUBUNIDAD",
                      "name": "INGEMMET — Geomorfología por región (SUBUNIDAD)"},
}
LICENSE = ("INGEMMET (copyright del servicio); sin licencia abierta declarada. Uso interno de investigación "
           "autorizado por el usuario; no redistribuir")
CHUNK = 100
MAX_FEATURES = 5000
SIMPLIFY_DEG = 0.0002
MIN_CLASS_AREA = 0.02     # clases con < 2 % del área se agrupan en «otras»
NO_CLASS = "(sin dato)"
USER_AGENT = "neuroambiental-ia/0.9 (investigacion interna)"


class GeologyError(Exception):
    pass


def _get(url: str, params: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    if urllib.parse.urlsplit(full).hostname != HOST:
        raise GeologyError("Host no permitido.")
    try:
        with urllib.request.urlopen(urllib.request.Request(full, headers={"User-Agent": USER_AGENT}), timeout=120) as r:
            raw = r.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GeologyError(f"No se pudo consultar INGEMMET: {exc}") from exc
    try:
        doc = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        doc = json.loads(raw.decode("latin-1"))  # algunos servicios antiguos responden en Latin-1
    except json.JSONDecodeError as exc:
        raise GeologyError("Respuesta no válida de INGEMMET.") from exc
    if "error" in doc:
        raise GeologyError(f"INGEMMET respondió con error: {doc['error'].get('message', '')[:200]}")
    return doc


def fetch_layer(kind: str, bbox: list[float]) -> dict:
    layer = LAYERS[kind]
    area = {"where": "1=1", "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects"}
    ids = sorted(_get(layer["url"], {**area, "returnIdsOnly": "true", "f": "json"}).get("objectIds") or [])
    if len(ids) > MAX_FEATURES:
        raise GeologyError(f"Demasiados polígonos ({len(ids)}); reduzca el recorte.")
    feats = []
    for i in range(0, len(ids), CHUNK):
        page = _get(layer["url"], {"objectIds": ",".join(str(x) for x in ids[i:i + CHUNK]),
                                   "outFields": layer["field"], "returnGeometry": "true", "outSR": "4326",
                                   "maxAllowableOffset": SIMPLIFY_DEG, "geometryPrecision": 6, "f": "geojson"})
        feats += page.get("features", [])
    return {"type": "FeatureCollection", "features": feats}


def class_of(props: dict, field: str) -> str:
    v = str((props or {}).get(field) or "").strip()
    return v or NO_CLASS


def import_layer(db: Session, user: User | None, kind: str, bbox: list[float], fetcher=None) -> DataRecord:
    if kind not in LAYERS:
        raise GeologyError(f"Capa desconocida: {kind}")
    fc = (fetcher or fetch_layer)(kind, bbox)
    if not fc["features"]:
        raise GeologyError("INGEMMET no devolvió polígonos para esa área.")
    field = LAYERS[kind]["field"]
    counts: dict[str, int] = {}
    for f in fc["features"]:
        c = class_of(f.get("properties"), field)
        counts[c] = counts.get(c, 0) + 1
    raw = json.dumps(fc, ensure_ascii=False).encode("utf-8")
    result = validate_geojson(raw)
    result.meta.update({"geology": kind, "field": field, "classes": counts, "bbox_consulta": bbox,
                        "simplificacion_grados": SIMPLIFY_DEG})
    return store_file(
        db, raw=raw, extension=".geojson", original_name=f"ingemmet_{kind}.geojson", result=result,
        source_name=LAYERS[kind]["name"], source_license=LICENSE,
        title=f"{kind.capitalize()} INGEMMET · {len(fc['features'])} polígonos · {len(counts)} clases",
        observed_at=None, is_simulated=False,
        provenance=(f"Consulta por recorte {bbox} a {LAYERS[kind]['url']} (campo {field}); geometrías "
                    f"simplificadas ≈20 m en el servidor. Clases con su nombre oficial, sin reinterpretar."),
        user_id=getattr(user, "id", None),
    )


def rasterize(fc: dict, field: str, arr: np.ndarray, bbox) -> tuple[np.ndarray, list[str]]:
    """Índice de clase por celda (0 = sin polígono) y la lista de nombres (índice i → names[i])."""
    names = [NO_CLASS]
    index = {NO_CLASS: 0}
    shapes = []
    for f in fc.get("features", []):
        g = f.get("geometry")
        if not g:
            continue
        c = class_of(f.get("properties"), field)
        if c not in index:
            index[c] = len(names)
            names.append(c)
        shapes.append((g, index[c]))
    dlon, dlat = demlib.cell_size(bbox, arr)
    out = features.rasterize(shapes, out_shape=arr.shape, transform=from_origin(bbox[0], bbox[3], dlon, dlat),
                             fill=0, dtype="int16")
    return out, names


def kept_classes(idx: np.ndarray, names: list[str]) -> list[int]:
    """Clases con ≥ MIN_CLASS_AREA del recorte (el resto se agrupa en «otras»)."""
    counts = np.bincount(idx.ravel(), minlength=len(names)) / idx.size
    return [i for i in range(len(names)) if counts[i] >= MIN_CLASS_AREA and names[i] != NO_CLASS]


def frequency_ratio(idx: np.ndarray, names: list[str], presences: np.ndarray) -> list[dict]:
    """Descriptivo (con TODOS los eventos, no validado): % de eventos en cada clase / % de área de la clase."""
    area = np.bincount(idx.ravel(), minlength=len(names)) / idx.size
    ev = np.bincount(idx[presences[:, 0], presences[:, 1]], minlength=len(names)) / max(len(presences), 1)
    rows = []
    for i, n in enumerate(names):
        if area[i] == 0:
            continue
        rows.append({"clase": n, "pct_area": round(float(area[i] * 100), 1), "pct_eventos": round(float(ev[i] * 100), 1),
                     "razon_frecuencia": round(float(ev[i] / area[i]), 2)})
    return sorted(rows, key=lambda r: -r["pct_area"])
