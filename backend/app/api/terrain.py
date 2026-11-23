"""API de NEUROTERRAIN: sensores, importación de mediciones (CSV de NEURODATA) y series de desplazamiento.

Indicadores EXPERIMENTALES; no son predicción de falla ni sustituyen el criterio geotécnico.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.lazy import lazy
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import Sensor, Territory, User

# Carga diferida: numpy solo se importa al usar sensores/series por primera vez.
service = lazy("app.modules.terrain.service")
series = lazy("app.modules.terrain.series")

router = APIRouter(prefix="/api/terrain", tags=["NEUROTERRAIN (movimientos territoriales)"])

SensorKind = Literal["gps", "inclinometro", "piezometro", "extensometro", "otro"]


class SensorIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    kind: SensorKind
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    territory_id: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Indique latitud y longitud juntas, o ninguna.")
        return self


class ImportIn(BaseModel):
    data_record_id: str = Field(min_length=32, max_length=32)
    format: Literal["largo", "ancho"] = "largo"
    date_column: str = Field(default="fecha", min_length=1, max_length=128)
    variable_column: str = Field(default="variable", max_length=128)
    value_column: str = Field(default="valor", max_length=128)
    unit_column: str | None = Field(default="unidad", max_length=128)
    value_columns: list[str] = Field(default_factory=list, max_length=50)  # formato ancho: una columna por variable
    units: dict[str, str] = Field(default_factory=dict)
    default_unit: str = Field(default="", max_length=32)
    normalize: bool = False  # ordena y descarta duplicados idénticos; los conflictivos siempre se rechazan

    @model_validator(mode="after")
    def _wide(self):
        if self.format == "ancho" and not self.value_columns:
            raise ValueError("En formato ancho indique value_columns (una columna por variable).")
        return self


class AnalysisParams(BaseModel):
    variable: str | None = Field(default=None, max_length=64)
    window_days: float = Field(default=30.0, gt=0, le=36500)
    vel_threshold: float = Field(default=0.05, gt=0)   # EJEMPLO configurable, unidad/día
    acc_ratio: float = Field(default=1.5, gt=1, le=100)  # EJEMPLO configurable
    k_mad: float = Field(default=6.0, ge=2, le=50)


class AlertIn(AnalysisParams):
    level: Literal["bajo", "medio", "alto"] | None = None
    notes: str = Field(default="", max_length=2000)


def _cfg(p: AnalysisParams, max_points: int = 2000):
    return series.Config(window_days=p.window_days, vel_threshold=p.vel_threshold, acc_ratio=p.acc_ratio,
                         k_mad=p.k_mad, max_points=max_points)


def _call(fn):
    try:
        return fn()
    except service.TerrainError as exc:
        db_msgs = exc.messages
        detail = {"message": db_msgs[0], "errors": db_msgs} if len(db_msgs) > 1 else db_msgs[0]
        raise HTTPException(exc.status_code, detail) from exc


@router.post("/sensors", status_code=201)
def create_sensor(body: SensorIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    if body.territory_id and db.get(Territory, body.territory_id) is None:
        raise HTTPException(422, "El territorio indicado no existe.")
    s = Sensor(name=body.name.strip(), kind=body.kind, latitude=body.latitude, longitude=body.longitude,
               territory_id=body.territory_id)
    db.add(s)
    db.flush()
    audit(db, "terrain_crear_sensor", user_id=user.id, target_type="sensor", target_id=s.id,
          details={"tipo": body.kind}, commit=False)
    db.commit()
    return service.sensor_dict(db, s)


@router.get("/sensors")
def list_sensors(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Sensor).order_by(Sensor.created_at.desc()).limit(500))
    return [service.sensor_dict(db, s) for s in rows]


@router.get("/sensors/{sensor_id}")
def get_sensor(sensor_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return service.sensor_dict(db, _call(lambda: service.get_sensor(db, sensor_id)))


@router.post("/sensors/{sensor_id}/import", status_code=201)
def import_csv(sensor_id: str, body: ImportIn, user: User = Depends(require_role("analista")),
               db: Session = Depends(get_db)) -> dict:
    sensor = _call(lambda: service.get_sensor(db, sensor_id))
    return _call(lambda: service.import_measurements(db, user, sensor, body.model_dump()))


@router.get("/sensors/{sensor_id}/series")
def sensor_series(sensor_id: str, variable: str | None = Query(default=None, max_length=64),
                  window_days: float = Query(30.0, gt=0, le=36500), vel_threshold: float = Query(0.05, gt=0),
                  acc_ratio: float = Query(1.5, gt=1, le=100), k_mad: float = Query(6.0, ge=2, le=50),
                  max_points: int = Query(2000, ge=10, le=2000), _: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> dict:
    sensor = _call(lambda: service.get_sensor(db, sensor_id))
    params = AnalysisParams(variable=variable, window_days=window_days, vel_threshold=vel_threshold,
                            acc_ratio=acc_ratio, k_mad=k_mad)
    return _call(lambda: service.analyze_sensor(db, sensor, variable, _cfg(params, max_points)))


@router.post("/sensors/{sensor_id}/alert", status_code=201)
def request_alert(sensor_id: str, body: AlertIn, user: User = Depends(require_role("analista")),
                  db: Session = Depends(get_db)) -> dict:
    """Crea una alerta EXPERIMENTAL solo a petición explícita de un analista (nunca automática)."""
    sensor = _call(lambda: service.get_sensor(db, sensor_id))
    alert = _call(lambda: service.create_alert(db, user, sensor, body.variable, _cfg(body), body.level, body.notes))
    return {"alert_id": alert.id, "level": alert.level, "alert_kind": alert.alert_kind,
            "validation_status": alert.validation_status, "is_simulated": alert.is_simulated, "title": alert.title,
            "evidence": alert.evidence, "uncertainty": alert.uncertainty, "aviso": series.AVISO}
