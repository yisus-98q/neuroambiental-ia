"""Inventario REAL de peligros geológicos: INGEMMET — GEOCATMIN «Peligros Geológicos del Perú» (feb. 2013).

- Servicio público ArcGIS REST, sin cuenta. Licencia NO declarada en el servicio (copyrightText vacío):
  el usuario autorizó su uso INTERNO de investigación, citando la fuente y sin redistribuir.
- Solo se consulta el servidor oficial (protección SSRF) y solo por recorte (bbox), paginado.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy.orm import Session

from app.models import DataRecord, User
from app.neurodata.service import store_file
from app.neurodata.validators import validate_geojson

SERVICE = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_PELIGROS_GEOLOGICOS/MapServer/0/query"
ALLOWED_HOST = "geocatmin.ingemmet.gob.pe"
SOURCE_NAME = "INGEMMET — GEOCATMIN Peligros Geológicos del Perú (feb. 2013)"
SOURCE_LICENSE = "No declarada por el servicio; uso interno de investigación autorizado por el usuario; no redistribuir"
FIELDS = ["COD_INV", "TIP_PELIGRO", "NOM_PELIGRO", "FECHA", "NM_DPTO", "NM_PROV", "NM_DIST", "NM_SECTOR",
          "FUENTE", "AUTOR", "TIESTU_ANO"]
PAGE = 1000
MAX_FEATURES = 20000
USER_AGENT = "neuroambiental-ia/0.9 (investigacion interna)"


class InventoryError(Exception):
    pass


def _get(params: dict) -> dict:
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    if urllib.parse.urlsplit(url).hostname != ALLOWED_HOST:
        raise InventoryError("Host no permitido.")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=90) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"No se pudo consultar INGEMMET: {exc}") from exc
    if "error" in doc:
        raise InventoryError(f"INGEMMET respondió con error: {doc['error'].get('message', '')[:200]}")
    return doc


def fetch_events(bbox: list[float]) -> dict:
    """FeatureCollection (EPSG:4326) de los eventos que intersecan el bbox, paginada."""
    # El servidor (ArcGIS antiguo) no admite resultOffset: primero se piden los OBJECTID del área y luego
    # los eventos por lotes de identificadores. Funciona con cualquier versión del servicio.
    area = {"where": "1=1", "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects"}
    ids = sorted(_get({**area, "returnIdsOnly": "true", "f": "json"}).get("objectIds") or [])[:MAX_FEATURES]
    features = []
    for i in range(0, len(ids), PAGE):
        chunk = ids[i:i + PAGE]
        page = _get({"objectIds": ",".join(str(x) for x in chunk), "outFields": ",".join(FIELDS),
                     "returnGeometry": "true", "outSR": "4326", "f": "geojson"})
        features += page.get("features", [])
    return {"type": "FeatureCollection", "features": features}


def import_events(db: Session, user: User | None, bbox: list[float], fetcher=fetch_events) -> DataRecord:
    fc = fetcher(bbox)
    if not fc["features"]:
        raise InventoryError("INGEMMET no devolvió eventos para esa área.")
    raw = json.dumps(fc, ensure_ascii=False).encode("utf-8")
    result = validate_geojson(raw)
    tipos: dict[str, int] = {}
    for f in fc["features"]:
        t = str((f.get("properties") or {}).get("TIP_PELIGRO") or "sin tipo")
        tipos[t] = tipos.get(t, 0) + 1
    result.meta.update({"inventory": True, "bbox_consulta": bbox, "tipos_peligro": tipos, "servicio": SERVICE})
    rec = store_file(
        db, raw=raw, extension=".geojson", original_name="ingemmet_peligros_geologicos.geojson", result=result,
        source_name=SOURCE_NAME, source_license=SOURCE_LICENSE,
        title=f"Inventario INGEMMET de peligros geológicos · {len(fc['features'])} eventos",
        observed_at=None, is_simulated=False,
        provenance=(f"Consulta por recorte {bbox} al servicio oficial {SERVICE} (GEOCATMIN, feb. 2013). "
                    "Eventos inventariados en campo y gabinete por INGEMMET. Licencia no declarada: uso interno."),
        user_id=getattr(user, "id", None),
    )
    return rec
