"""Validación de archivos entrantes. Solo librería estándar (bajo consumo de RAM)."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

ALLOWED_EXTENSIONS = {
    ".csv": "csv",
    ".geojson": "geojson",
    ".json": "geojson",
    ".png": "imagen",
    ".jpg": "imagen",
    ".jpeg": "imagen",
    ".pdf": "documento",
}
LAT_NAMES = {"lat", "latitud", "latitude", "y"}
LON_NAMES = {"lon", "lng", "long", "longitud", "longitude", "x"}
GEOMETRY_TYPES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon",
                  "GeometryCollection"}


@dataclass
class ValidationResult:
    valid: bool
    data_type: str
    file_format: str
    messages: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    bbox: list[float] | None = None


def valid_lat_lon(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


class _BBox:
    def __init__(self) -> None:
        self.v: list[float] | None = None

    def add(self, lon: float, lat: float) -> None:
        if self.v is None:
            self.v = [lon, lat, lon, lat]
        else:
            self.v = [min(self.v[0], lon), min(self.v[1], lat), max(self.v[2], lon), max(self.v[3], lat)]


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def find_lat_lon_columns(headers: list[str]) -> tuple[str | None, str | None]:
    norm = {h.strip().lower(): h for h in headers}
    lat = next((norm[n] for n in norm if n in LAT_NAMES), None)
    lon = next((norm[n] for n in norm if n in LON_NAMES), None)
    return lat, lon


def read_csv_rows(raw: bytes) -> tuple[list[str], list[dict]]:
    text = _decode(raw)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    return headers, list(reader)


def validate_csv(raw: bytes, max_rows: int) -> ValidationResult:
    res = ValidationResult(valid=True, data_type="csv", file_format="text/csv")
    try:
        headers, rows = read_csv_rows(raw)
    except (csv.Error, UnicodeError) as exc:
        return ValidationResult(False, "csv", "text/csv", [f"CSV ilegible: {exc}"])
    if not headers or all(not h.strip() for h in headers):
        return ValidationResult(False, "csv", "text/csv", ["El CSV no tiene encabezados."])
    if len(set(h.strip().lower() for h in headers)) != len(headers):
        res.messages.append("Hay encabezados duplicados.")
        res.valid = False
    if not rows:
        res.messages.append("El CSV no contiene filas de datos.")
        res.valid = False
    if len(rows) > max_rows:
        res.messages.append(f"El CSV supera el máximo de {max_rows} filas ({len(rows)}).")
        res.valid = False
    lat_col, lon_col = find_lat_lon_columns(headers)
    res.meta = {"rows": len(rows), "columns": headers, "lat_column": lat_col, "lon_column": lon_col}
    if lat_col and lon_col:
        bbox, bad = _BBox(), 0
        for row in rows:
            try:
                lat, lon = float(row[lat_col]), float(row[lon_col])
            except (TypeError, ValueError):
                bad += 1
                continue
            if valid_lat_lon(lat, lon):
                bbox.add(lon, lat)
            else:
                bad += 1
        res.bbox = bbox.v
        res.meta["invalid_coordinate_rows"] = bad
        if bad:
            res.messages.append(f"{bad} fila(s) con coordenadas inválidas o fuera de rango.")
            if bbox.v is None:
                res.valid = False
    else:
        res.messages.append("No se detectaron columnas de latitud/longitud: el CSV no se mostrará en el mapa.")
    return res


def _walk_coords(coords, bbox: _BBox) -> int:
    """Recorre coordenadas anidadas; devuelve cuántos puntos están fuera de rango."""
    if isinstance(coords, (list, tuple)) and len(coords) >= 2 and all(
        isinstance(c, (int, float)) and not isinstance(c, bool) for c in coords[:2]
    ):
        lon, lat = float(coords[0]), float(coords[1])
        if valid_lat_lon(lat, lon):
            bbox.add(lon, lat)
            return 0
        return 1
    if isinstance(coords, (list, tuple)):
        return sum(_walk_coords(c, bbox) for c in coords)
    raise ValueError("coordenadas mal formadas")


def _check_geometry(geom, bbox: _BBox) -> int:
    if geom is None:
        return 0
    if not isinstance(geom, dict) or geom.get("type") not in GEOMETRY_TYPES:
        raise ValueError("geometría con tipo inválido")
    if geom["type"] == "GeometryCollection":
        return sum(_check_geometry(g, bbox) for g in geom.get("geometries", []))
    if "coordinates" not in geom:
        raise ValueError("geometría sin 'coordinates'")
    return _walk_coords(geom["coordinates"], bbox)


def validate_geojson(raw: bytes) -> ValidationResult:
    fmt = "application/geo+json"
    try:
        doc = json.loads(_decode(raw))
    except json.JSONDecodeError as exc:
        return ValidationResult(False, "geojson", fmt, [f"JSON inválido: {exc.msg} (línea {exc.lineno})."])
    if not isinstance(doc, dict) or "type" not in doc:
        return ValidationResult(False, "geojson", fmt, ["No es un objeto GeoJSON (falta 'type')."])
    if doc["type"] == "FeatureCollection":
        features = doc.get("features")
        if not isinstance(features, list):
            return ValidationResult(False, "geojson", fmt, ["'features' debe ser una lista."])
    elif doc["type"] == "Feature":
        features = [doc]
    elif doc["type"] in GEOMETRY_TYPES:
        features = [{"type": "Feature", "geometry": doc, "properties": {}}]
    else:
        return ValidationResult(False, "geojson", fmt, [f"Tipo GeoJSON no soportado: {doc['type']}"])
    bbox, out_of_range, geom_types = _BBox(), 0, set()
    try:
        for i, f in enumerate(features):
            if not isinstance(f, dict) or f.get("type") != "Feature":
                raise ValueError(f"el elemento {i} no es un Feature")
            out_of_range += _check_geometry(f.get("geometry"), bbox)
            if f.get("geometry"):
                geom_types.add(f["geometry"]["type"])
    except ValueError as exc:
        return ValidationResult(False, "geojson", fmt, [f"GeoJSON inválido: {exc}."])
    res = ValidationResult(True, "geojson", fmt, bbox=bbox.v)
    res.meta = {"features": len(features), "geometry_types": sorted(geom_types)}
    if out_of_range:
        res.valid = False
        res.messages.append(f"{out_of_range} coordenada(s) fuera de rango (se espera EPSG:4326 lon/lat).")
    if not features:
        res.messages.append("La colección no tiene elementos.")
    return res


def validate_image(raw: bytes) -> ValidationResult:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        meta = {}
        if len(raw) >= 24 and raw[12:16] == b"IHDR":
            meta = {"width": int.from_bytes(raw[16:20], "big"), "height": int.from_bytes(raw[20:24], "big")}
        return ValidationResult(True, "imagen", "image/png", meta=meta)
    if raw.startswith(b"\xff\xd8\xff"):
        return ValidationResult(True, "imagen", "image/jpeg")
    return ValidationResult(False, "imagen", "desconocido",
                            ["El contenido no corresponde a una imagen PNG o JPG válida."])


def validate_pdf(raw: bytes) -> ValidationResult:
    if raw.startswith(b"%PDF-"):
        return ValidationResult(True, "documento", "application/pdf", meta={"pdf_version": raw[5:8].decode(errors="replace")})
    return ValidationResult(False, "documento", "desconocido", ["El contenido no es un PDF válido."])


def validate_file(extension: str, raw: bytes, max_csv_rows: int) -> ValidationResult:
    kind = ALLOWED_EXTENSIONS.get(extension.lower())
    if kind == "csv":
        return validate_csv(raw, max_csv_rows)
    if kind == "geojson":
        return validate_geojson(raw)
    if kind == "imagen":
        return validate_image(raw)
    if kind == "documento":
        return validate_pdf(raw)
    return ValidationResult(False, "desconocido", "desconocido", [f"Extensión no permitida: {extension}"])
