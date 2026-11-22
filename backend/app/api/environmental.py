from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, Run, User
from app.modules.environmental import raster, remote, service

router = APIRouter(prefix="/api/environmental", tags=["Predicción Ambiental"])

# Área por defecto: Huaraz y quebradas de la Cordillera Blanca (aprox.).
DEFAULT_BBOX = [-77.60, -9.60, -77.30, -9.35]
MAX_SPAN_DEG = 0.5


class BBoxModel(BaseModel):
    bbox: list[float] = Field(default_factory=lambda: list(DEFAULT_BBOX), min_length=4, max_length=4)

    @field_validator("bbox")
    @classmethod
    def _valid_bbox(cls, v: list[float]):
        minx, miny, maxx, maxy = v
        if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
            raise ValueError("bbox debe ser [minLon, minLat, maxLon, maxLat] con valores válidos.")
        if maxx - minx > MAX_SPAN_DEG or maxy - miny > MAX_SPAN_DEG:
            raise ValueError(f"El área máxima es {MAX_SPAN_DEG}° x {MAX_SPAN_DEG}° (protege memoria y descargas).")
        return v


class SearchIn(BBoxModel):
    date_from: date
    date_to: date
    max_cloud: float = Field(default=20, ge=0, le=100)

    @model_validator(mode="after")
    def _dates(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from debe ser anterior a date_to.")
        if self.date_to > date.today():
            raise ValueError("date_to no puede estar en el futuro.")
        return self


class NdviIn(BBoxModel):
    item_id: str = Field(min_length=10, max_length=64)
    resolution_deg: float = Field(default=0.0003, ge=0.0001, le=0.005)


class ChangeIn(BaseModel):
    before_id: str = Field(min_length=32, max_length=32)
    after_id: str = Field(min_length=32, max_length=32)
    threshold: float = Field(default=0.2, ge=0.05, le=0.8)


def _record_out(r: DataRecord) -> dict:
    return {"id": r.id, "data_type": r.data_type, "title": r.title, "bbox": r.bbox, "observed_at": r.observed_at,
            "received_at": r.received_at, "is_simulated": r.is_simulated, "provenance": r.provenance,
            "source": r.source.name if r.source else "", "extra": r.extra}


def _handle(fn):
    try:
        return fn()
    except service.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except (raster.GridError, service.ProcessingError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except remote.RemoteError as exc:
        raise HTTPException(502, f"Servicio de imágenes no disponible: {exc}") from exc


@router.get("/defaults")
def defaults() -> dict:
    return {"bbox": DEFAULT_BBOX, "area_name": "Huaraz / Cordillera Blanca (aprox.)", "resolution_deg": 0.0003,
            "max_span_deg": MAX_SPAN_DEG, "source": service.SOURCE_NAME, "source_url": service.SOURCE_URL}


@router.post("/scenes/search")
def search(body: SearchIn, _: User = Depends(require_role("analista"))) -> list[dict]:
    scenes = _handle(lambda: remote.search_scenes(body.bbox, body.date_from.isoformat(), body.date_to.isoformat(),
                                                  body.max_cloud))
    return [s.public() for s in scenes]


@router.post("/ndvi", status_code=201)
def ndvi(body: NdviIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    rec = _handle(lambda: service.compute_ndvi(db, user, item_id=body.item_id, bbox=body.bbox,
                                               res=body.resolution_deg))
    return _record_out(rec)


@router.post("/change", status_code=201)
def change(body: ChangeIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    rec = _handle(lambda: service.compute_change(db, user, before_id=body.before_id, after_id=body.after_id,
                                                 threshold=body.threshold))
    return _record_out(rec)


@router.get("/rasters")
def rasters(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = (select(DataRecord).where(DataRecord.data_type.in_(("raster_ndvi", "raster_cambio")))
         .order_by(DataRecord.received_at.desc()).limit(100))
    return [_record_out(r) for r in db.scalars(q)]


@router.get("/analyses")
def analyses(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = select(Run).where(Run.module_key == "environmental").order_by(Run.started_at.desc()).limit(50)
    return [{"id": r.id, "run_type": r.run_type, "status": r.status, "started_at": r.started_at,
             "finished_at": r.finished_at, "parameters": r.parameters, "result_summary": r.result_summary}
            for r in db.scalars(q)]
