"""Servicios de NEURODATA: almacenamiento local, fuentes y capas para el mapa."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DataRecord, Document, Source
from app.models.common import new_id, utcnow
from app.neurodata.validators import ValidationResult, find_lat_lon_columns, read_csv_rows, valid_lat_lon

MAX_LAYER_FEATURES = 5000


class UploadRejected(Exception):
    def __init__(self, messages: list[str], status_code: int = 422):
        super().__init__("; ".join(messages))
        self.messages = messages
        self.status_code = status_code


def get_or_create_source(db: Session, name: str, kind: str, license_: str = "desconocida", url: str = "") -> Source:
    src = db.scalar(select(Source).where(Source.name == name))
    if src is None:
        src = Source(name=name, kind=kind, license=license_, url=url)
        db.add(src)
        db.flush()
    elif src.license == "desconocida" and license_ and license_ != "desconocida":
        # Completa la licencia si antes no se conocía; nunca sobrescribe una ya registrada.
        src.license = license_
    return src


def _uploads_root() -> Path:
    root = settings.uploads_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_file(
    db: Session,
    *,
    raw: bytes,
    extension: str,
    original_name: str,
    result: ValidationResult,
    source_name: str,
    source_license: str,
    title: str,
    observed_at: datetime | None,
    is_simulated: bool,
    provenance: str,
    user_id: str | None,
    module_key: str | None = None,
) -> DataRecord:
    if not result.valid:
        raise UploadRejected(result.messages or ["Archivo inválido."])
    record_id = new_id()
    now = utcnow()
    rel = Path(f"{now:%Y}") / f"{now:%m}" / f"{record_id}{extension.lower()}"
    dest = _uploads_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)

    source = get_or_create_source(db, source_name, "archivo", source_license)
    lat = lon = None
    if result.bbox and result.bbox[0] == result.bbox[2] and result.bbox[1] == result.bbox[3]:
        lon, lat = result.bbox[0], result.bbox[1]
    record = DataRecord(
        id=record_id,
        source_id=source.id,
        data_type=result.data_type,
        title=title or original_name,
        latitude=lat,
        longitude=lon,
        bbox=result.bbox,
        observed_at=observed_at,
        file_format=result.file_format,
        validation_status="valido",
        validation_messages=result.messages,
        provenance=provenance or f"Archivo cargado: {original_name}",
        is_simulated=is_simulated,
        file_path=rel.as_posix(),
        file_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        extra={"original_name": original_name, **result.meta},
        created_by=user_id,
    )
    db.add(record)
    if result.data_type == "documento" or (module_key == "construction"):
        db.add(Document(data_record_id=record_id, module_key=module_key or "construction"))
    db.flush()
    return record


def absolute_path(record: DataRecord) -> Path:
    path = (settings.uploads_dir / (record.file_path or "")).resolve()
    if settings.uploads_dir.resolve() not in path.parents:
        raise ValueError("Ruta fuera del directorio de cargas.")
    return path


def _props(record: DataRecord, extra: dict | None = None) -> dict:
    return {
        "record_id": record.id,
        "title": record.title,
        "data_type": record.data_type,
        "is_simulated": record.is_simulated,
        "source": record.source.name if record.source else "",
        **(extra or {}),
    }


def record_features(record: DataRecord, limit: int = MAX_LAYER_FEATURES) -> list[dict]:
    """Convierte un registro en features GeoJSON. Solo datos reales del registro."""
    if record.validation_status != "valido":
        return []
    if record.data_type == "geojson" and record.file_path:
        doc = json.loads(absolute_path(record).read_text(encoding="utf-8-sig"))
        if doc.get("type") == "FeatureCollection":
            feats = doc.get("features", [])
        elif doc.get("type") == "Feature":
            feats = [doc]
        else:
            feats = [{"type": "Feature", "geometry": doc, "properties": {}}]
        out = []
        for f in feats[:limit]:
            out.append({"type": "Feature", "geometry": f.get("geometry"),
                        "properties": _props(record, f.get("properties") or {})})
        return out
    if record.data_type == "csv" and record.file_path:
        headers, rows = read_csv_rows(absolute_path(record).read_bytes())
        lat_col, lon_col = find_lat_lon_columns(headers)
        if not (lat_col and lon_col):
            return []
        out = []
        for row in rows:
            try:
                lat, lon = float(row[lat_col]), float(row[lon_col])
            except (TypeError, ValueError):
                continue
            if not valid_lat_lon(lat, lon):
                continue
            props = {k: v for k, v in row.items() if k not in (lat_col, lon_col) and k is not None}
            out.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": _props(record, props)})
            if len(out) >= limit:
                break
        return out
    if record.latitude is not None and record.longitude is not None:
        extra = {"value": record.value, "unit": record.unit}
        return [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [record.longitude, record.latitude]},
                 "properties": _props(record, extra)}]
    return []
