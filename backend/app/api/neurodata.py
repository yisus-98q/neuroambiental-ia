from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, Measurement, Source, User
from app.models.common import utcnow
from app.neurodata.service import (
    MAX_LAYER_FEATURES,
    UploadRejected,
    absolute_path,
    get_or_create_source,
    record_features,
    store_file,
)
from app.neurodata.validators import ALLOWED_EXTENSIONS, validate_file
from app.schemas import DataRecordOut, ManualRecordIn, SourceOut

router = APIRouter(prefix="/api/neurodata", tags=["NEURODATA ENGINE"])


def _out(r: DataRecord) -> DataRecordOut:
    out = DataRecordOut.model_validate(r)
    out.source_name = r.source.name if r.source else ""
    return out


def _get(db: Session, record_id: str) -> DataRecord:
    r = db.get(DataRecord, record_id)
    if r is None:
        raise HTTPException(404, "Registro no encontrado.")
    return r


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    chunks, size = [], 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"El archivo supera el máximo de {settings.max_upload_mb} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=DataRecordOut, status_code=201)
async def upload(
    file: UploadFile = File(...),
    source_name: str = Form(..., min_length=1, max_length=128),
    is_simulated: bool = Form(...),
    source_license: str = Form("desconocida", max_length=128),
    title: str = Form("", max_length=256),
    observed_at: datetime | None = Form(None),
    provenance: str = Form("", max_length=2000),
    module_key: str | None = Form(None, max_length=32),
    user: User = Depends(require_role("analista")),
    db: Session = Depends(get_db),
) -> DataRecordOut:
    original = Path(file.filename or "").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(415, f"Extensión no permitida '{ext or '(ninguna)'}'. Permitidas: {allowed}")
    raw = await _read_limited(file, settings.max_upload_bytes)
    if not raw:
        raise HTTPException(422, "El archivo está vacío.")
    result = validate_file(ext, raw, settings.max_csv_rows)
    try:
        record = store_file(db, raw=raw, extension=ext, original_name=original, result=result,
                            source_name=source_name.strip(), source_license=source_license.strip(),
                            title=title.strip(), observed_at=observed_at, is_simulated=is_simulated,
                            provenance=provenance.strip(), user_id=user.id, module_key=module_key)
    except UploadRejected as exc:
        db.rollback()
        audit(db, "carga_rechazada", user_id=user.id, target_type="archivo", success=False,
              details={"archivo": original, "motivos": exc.messages})
        raise HTTPException(exc.status_code, {"message": "Archivo rechazado.", "errors": exc.messages}) from exc
    audit(db, "carga_archivo", user_id=user.id, target_type="data_record", target_id=record.id,
          details={"archivo": original, "tipo": record.data_type, "simulado": is_simulated}, commit=False)
    db.commit()
    return _out(record)


@router.post("/records/manual", response_model=DataRecordOut, status_code=201)
def manual_record(body: ManualRecordIn, user: User = Depends(require_role("analista")),
                  db: Session = Depends(get_db)) -> DataRecordOut:
    source = get_or_create_source(db, body.source_name.strip(), "carga_manual")
    record = DataRecord(
        source_id=source.id, data_type="medicion_manual", title=body.title, territory_id=body.territory_id,
        latitude=body.latitude, longitude=body.longitude, observed_at=body.observed_at, unit=body.unit,
        value=body.value, file_format="manual", validation_status="valido", quality=body.quality,
        provenance=body.provenance or "Registro manual", is_simulated=body.is_simulated,
        extra={"variable": body.variable} if body.variable else {}, created_by=user.id,
    )
    db.add(record)
    db.flush()
    if body.variable and body.value is not None:
        db.add(Measurement(data_record_id=record.id, variable=body.variable, value=body.value, unit=body.unit,
                           observed_at=body.observed_at or utcnow(), is_simulated=body.is_simulated))
    audit(db, "registro_manual", user_id=user.id, target_type="data_record", target_id=record.id, commit=False)
    db.commit()
    db.refresh(record)
    return _out(record)


@router.get("/records", response_model=list[DataRecordOut])
def list_records(data_type: str | None = None, is_simulated: bool | None = None, limit: int = 100,
                 offset: int = 0, _: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[DataRecordOut]:
    q = select(DataRecord).order_by(DataRecord.received_at.desc())
    if data_type:
        q = q.where(DataRecord.data_type == data_type)
    if is_simulated is not None:
        q = q.where(DataRecord.is_simulated.is_(is_simulated))
    q = q.limit(min(max(limit, 1), 500)).offset(max(offset, 0))
    return [_out(r) for r in db.scalars(q)]


@router.get("/records/{record_id}", response_model=DataRecordOut)
def get_record(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DataRecordOut:
    return _out(_get(db, record_id))


@router.get("/records/{record_id}/file")
def download(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    r = _get(db, record_id)
    if not r.file_path:
        raise HTTPException(404, "Este registro no tiene archivo.")
    path = absolute_path(r)
    if not path.is_file():
        raise HTTPException(410, "El archivo ya no existe en el almacenamiento local.")
    return FileResponse(path, media_type=r.file_format or None,
                        filename=r.extra.get("original_name", path.name))


@router.get("/records/{record_id}/preview")
def preview(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    """Vista previa PNG (RGBA, EPSG:4326, alineada con bbox) de un raster NDVI o de cambio."""
    r = _get(db, record_id)
    if not r.data_type.startswith("raster_") or not r.file_path:
        raise HTTPException(404, "Este registro no tiene vista previa.")
    path = absolute_path(r).with_suffix(".png")
    if not path.is_file():
        raise HTTPException(410, "La vista previa ya no existe en el almacenamiento local.")
    return FileResponse(path, media_type="image/png")


@router.get("/records/{record_id}/geojson")
def record_geojson(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"type": "FeatureCollection", "features": record_features(_get(db, record_id))}


@router.get("/layers")
def layers(include_simulated: bool = True, _: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> list[dict]:
    """Una capa por registro georreferenciado (máx. 50 capas, 5000 elementos cada una)."""
    q = (select(DataRecord).where(DataRecord.validation_status == "valido")
         .where((DataRecord.bbox.is_not(None)) | (DataRecord.latitude.is_not(None)))
         .order_by(DataRecord.received_at.desc()).limit(50))
    if not include_simulated:
        q = q.where(DataRecord.is_simulated.is_(False))
    out = []
    for r in db.scalars(q):
        feats = record_features(r, MAX_LAYER_FEATURES)
        if feats:
            out.append({"record_id": r.id, "title": r.title, "data_type": r.data_type,
                        "is_simulated": r.is_simulated, "source": r.source.name,
                        "geojson": {"type": "FeatureCollection", "features": feats}})
    return out


@router.get("/sources", response_model=list[SourceOut])
def sources(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Source]:
    return list(db.scalars(select(Source).order_by(Source.name)))


@router.get("/limits")
def limits() -> dict:
    return {"max_upload_mb": settings.max_upload_mb, "max_csv_rows": settings.max_csv_rows,
            "allowed_extensions": sorted(ALLOWED_EXTENSIONS)}
