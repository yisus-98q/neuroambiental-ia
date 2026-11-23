"""NEUROCONSTRUCTION: análisis preliminar de sitio sobre un DEM registrado (no reemplaza estudios oficiales)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.lazy import lazy
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, User

# Carga diferida: rasterio/scipy solo se importan al analizar un sitio.
site = lazy("app.modules.construction.site")
service = lazy("app.modules.neuro3d.service")
dem = lazy("app.modules.neuro3d.dem")

router = APIRouter(prefix="/api/construction", tags=["NEUROCONSTRUCTION"])
RISE_MIN, RISE_MAX = 0.5, 50.0
NOTICE = "No reemplaza evaluaciones profesionales ni autorizaciones oficiales."


class PointIn(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class FloodIn(PointIn):
    rise_m: float = Field(ge=RISE_MIN, le=RISE_MAX)


class SiteIn(BaseModel):
    dem_id: str = Field(min_length=32, max_length=32)
    point: PointIn | None = None
    geojson: dict | None = None
    buffer_m: float = Field(default=500, ge=0, le=5000)
    flood: FloodIn | None = None
    name: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def _one_site(self):
        if (self.point is None) == (self.geojson is None):
            raise ValueError("Indique un punto o un polígono GeoJSON (solo uno).")
        if self.geojson is not None and not site.geojson_size_ok(self.geojson):
            raise ValueError("El GeoJSON es demasiado grande (máx. ~200 KB).")
        return self


def _out(r: DataRecord) -> dict:
    return {"id": r.id, "title": r.title, "received_at": r.received_at, "latitude": r.latitude,
            "longitude": r.longitude, "is_simulated": r.is_simulated, "provenance": r.provenance,
            "extra": r.extra, "notice": NOTICE}


def _handle(fn):
    try:
        return fn()
    except service.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except (dem.DemError, service.ProcessingError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/site-analysis", status_code=201)
def site_analysis(body: SiteIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: site.run_site_analysis(
        db, user, dem_id=body.dem_id, point=body.point.model_dump() if body.point else None, geojson=body.geojson,
        buffer_m=body.buffer_m, flood=body.flood.model_dump() if body.flood else None, name=body.name)))


@router.get("/analyses")
def analyses(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [_out(r) for r in site.list_analyses(db)]
