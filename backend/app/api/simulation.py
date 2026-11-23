"""API de escenarios simplificados (SIMULACIÓN, no predicción): susceptibilidad, inundación y comparador."""
from __future__ import annotations

from typing import Annotated, Literal, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import DataRecord, User
from app.core.lazy import lazy

# Carga diferida: scipy/rasterio solo se importan al calcular escenarios.
scenarios = lazy("app.modules.neuro3d.scenarios")
service = lazy("app.modules.neuro3d.service")
dem = lazy("app.modules.neuro3d.dem")
RISE_MIN, RISE_MAX = 0.5, 50.0  # iguales a scenarios.RISE_MIN/MAX (se vuelven a validar)

router = APIRouter(prefix="/api/simulation", tags=["Simulación (escenarios)"])


class SuscParams(BaseModel):
    w_pendiente: float = Field(default=0.6, ge=0, le=1)
    w_vegetacion: float = Field(default=0.4, ge=0, le=1)
    umbral_medio: float = Field(default=0.33, gt=0, lt=1)
    umbral_alto: float = Field(default=0.66, gt=0, lt=1)

    @model_validator(mode="after")
    def _check(self):
        try:
            scenarios.check_susceptibility_params(self.w_pendiente, self.w_vegetacion, self.umbral_medio,
                                                  self.umbral_alto)
        except dem.DemError as exc:
            raise ValueError(str(exc)) from exc
        return self


class FloodParams(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    rise_m: float = Field(ge=RISE_MIN, le=RISE_MAX)


class SuscIn(SuscParams):
    dem_id: str = Field(min_length=32, max_length=32)
    ndvi_id: str | None = Field(default=None, min_length=32, max_length=32)


class FloodIn(FloodParams):
    dem_id: str = Field(min_length=32, max_length=32)


class SuscCfg(SuscParams):
    kind: Literal["susceptibilidad"]
    label: str = Field(default="", max_length=60)


class FloodCfg(FloodParams):
    kind: Literal["inundacion_demostrativa"]
    label: str = Field(default="", max_length=60)


class CompareIn(BaseModel):
    dem_id: str = Field(min_length=32, max_length=32)
    ndvi_id: str | None = Field(default=None, min_length=32, max_length=32)
    configs: list[Annotated[Union[SuscCfg, FloodCfg], Field(discriminator="kind")]] = Field(min_length=2, max_length=4)


def _out(r: DataRecord) -> dict:
    return {"id": r.id, "data_type": r.data_type, "title": r.title, "bbox": r.bbox, "received_at": r.received_at,
            "is_simulated": r.is_simulated, "provenance": r.provenance, "sha256": r.sha256, "extra": r.extra,
            "banner": scenarios.BANNER}


def _handle(fn):
    try:
        return fn()
    except service.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except (dem.DemError, service.ProcessingError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/susceptibility", status_code=201)
def susceptibility(body: SuscIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: scenarios.run_susceptibility(
        db, user, dem_id=body.dem_id, ndvi_id=body.ndvi_id, w_slope=body.w_pendiente, w_veg=body.w_vegetacion,
        t_mid=body.umbral_medio, t_high=body.umbral_alto)))


@router.post("/flood", status_code=201)
def flood(body: FloodIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _out(_handle(lambda: scenarios.run_flood(db, user, dem_id=body.dem_id, lon=body.lon, lat=body.lat,
                                                    rise_m=body.rise_m)))


@router.post("/compare")
def compare(body: CompareIn, _: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: scenarios.compare(db, dem_id=body.dem_id, ndvi_id=body.ndvi_id,
                                             configs=[c.model_dump() for c in body.configs]))


@router.get("/scenarios")
def list_scenarios(dem_id: str | None = Query(default=None, max_length=32), _: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> list[dict]:
    return [_out(r) for r in scenarios.list_scenario_records(db, dem_id)]


@router.get("/scenarios/{record_id}/grid")
def grid(record_id: str, max_size: int = Query(256, ge=16, le=512), _: User = Depends(get_current_user),
         db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: scenarios.scenario_grid(db, record_id, max_size))


@router.get("/scenarios/{record_id}/preview")
def preview(record_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return FileResponse(_handle(lambda: scenarios.preview_path(db, record_id)), media_type="image/png")
