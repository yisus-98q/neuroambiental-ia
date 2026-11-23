from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, User
from app.modules.neurovision import processing, service

router = APIRouter(prefix="/api/neurovision", tags=["NEUROVISION"])


class AnalyzeIn(BaseModel):
    record_id: str = Field(min_length=32, max_length=32)
    operation: str = Field(min_length=1, max_length=32)
    params: dict | None = None


class CompareIn(BaseModel):
    record_a: str = Field(min_length=32, max_length=32)
    record_b: str = Field(min_length=32, max_length=32)


def _out(r: DataRecord) -> dict:
    return {"id": r.id, "data_type": r.data_type, "title": r.title, "received_at": r.received_at,
            "is_simulated": r.is_simulated, "provenance": r.provenance, "sha256": r.sha256,
            "file_size": r.file_size, "source": r.source.name if r.source else "",
            "image_url": f"/api/neurodata/records/{r.id}/file",
            "overlay_url": f"/api/neurovision/results/{r.id}/overlay" if (r.extra or {}).get("overlay") else None,
            "extra": r.extra}


def _handle(fn):
    try:
        return fn()
    except service.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (processing.ImageError, processing.ParamError, processing.AlignError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/operations")
def operations(_: User = Depends(get_current_user)) -> dict:
    return {"operations": processing.public_operations(), "max_side_px": processing.MAX_SIDE,
            "max_megapixels": processing.MAX_PIXELS // 1_000_000, "confidence_note": processing.CONFIDENCE_NOTE,
            "limitations": processing.LIMITATIONS, "opencv_version": processing.OPENCV_VERSION}


@router.post("/analyze", status_code=201)
def analyze(body: AnalyzeIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: service.analyze(db, user, record_id=body.record_id, operation=body.operation,
                                                params=body.params)))


@router.post("/compare", status_code=201)
def compare(body: CompareIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: service.compare(db, user, record_a=body.record_a, record_b=body.record_b)))


@router.get("/results")
def results(limit: int = 50, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = (select(DataRecord).where(DataRecord.data_type == "imagen_procesada")
         .order_by(DataRecord.received_at.desc()).limit(min(max(limit, 1), 100)))
    out = []
    for r in db.scalars(q):
        item = _out(r)
        if isinstance(item.get("extra"), dict) and "regions" in item["extra"]:
            # El listado no incluye las regiones (hasta 200 por resultado): se consultan por registro.
            item["extra"] = {k: v for k, v in item["extra"].items() if k != "regions"}
        out.append(item)
    return out


@router.get("/results/{record_id}/overlay")
def overlay(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    rec = db.get(DataRecord, record_id)
    if rec is None or rec.data_type != "imagen_procesada":
        raise HTTPException(404, "Resultado no encontrado.")
    try:
        return FileResponse(service.overlay_path(rec), media_type="image/png")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
