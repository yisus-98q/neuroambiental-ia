from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, User
from app.modules.environmental import remote
from app.modules.neuro3d import service
from app.modules.neuro3d.dem import DemError

router = APIRouter(prefix="/api/neuro3d", tags=["NEURO 3D LAB"])

DEFAULT_BBOX = [-77.60, -9.60, -77.30, -9.35]
MAX_SPAN_DEG = 0.5


class TerrainIn(BaseModel):
    bbox: list[float] = Field(default_factory=lambda: list(DEFAULT_BBOX), min_length=4, max_length=4)
    resolution_deg: float = Field(default=0.0009, ge=0.0003, le=0.01)

    @field_validator("bbox")
    @classmethod
    def _valid_bbox(cls, v: list[float]):
        minx, miny, maxx, maxy = v
        if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
            raise ValueError("bbox debe ser [minLon, minLat, maxLon, maxLat] con valores válidos.")
        if maxx - minx > MAX_SPAN_DEG or maxy - miny > MAX_SPAN_DEG:
            raise ValueError(f"El área máxima es {MAX_SPAN_DEG}° x {MAX_SPAN_DEG}°.")
        return v


class FlowIn(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


def _out(r: DataRecord) -> dict:
    return {"id": r.id, "data_type": r.data_type, "title": r.title, "bbox": r.bbox, "received_at": r.received_at,
            "is_simulated": r.is_simulated, "provenance": r.provenance, "source": r.source.name if r.source else "",
            "sha256": r.sha256, "extra": r.extra}


def _handle(fn):
    try:
        return fn()
    except service.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except (DemError, service.ProcessingError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except remote.RemoteError as exc:
        raise HTTPException(502, f"Servicio de DEM no disponible: {exc}") from exc


@router.get("/defaults")
def defaults(_: User = Depends(get_current_user)) -> dict:
    return {"bbox": DEFAULT_BBOX, "area_name": "Huaraz / Cordillera Blanca (aprox.)", "resolution_deg": 0.0009,
            "max_span_deg": MAX_SPAN_DEG, "source": service.SOURCE_NAME, "attribution": service.ATTRIBUTION}


@router.post("/terrain", status_code=201)
def terrain(body: TerrainIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: service.fetch_dem(db, user, bbox=body.bbox, res=body.resolution_deg)))


@router.get("/terrains")
def terrains(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [_out(r) for r in service.list_terrains(db)]


@router.get("/terrains/{record_id}/mesh")
def mesh(record_id: str, max_size: int = Query(256, ge=16, le=512), _: User = Depends(get_current_user),
         db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: service.build_mesh(db, record_id, max_size))


@router.post("/terrains/{record_id}/flow-path", status_code=201)
def flow_path(record_id: str, body: FlowIn, user: User = Depends(require_role("analista")),
              db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: service.run_flow_path(db, user, record_id, body.lon, body.lat))


@router.get("/scenarios")
def scenarios(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_scenarios(db)


@router.get("/scenarios/{run_id}")
def scenario(run_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: service.get_scenario(db, run_id))
