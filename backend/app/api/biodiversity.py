"""API de biodiversidad (/api/biodiversity): especies, observaciones, validación, capa de mapa y resumen."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import Territory, User
from app.models.biodiversity import CONSERVATION_CATEGORIES, Observation, Species
from app.models.common import utcnow
from app.modules.biodiversity import service

router = APIRouter(prefix="/api/biodiversity", tags=["BIODIVERSIDAD"])

Method = Literal["avistamiento", "camara_trampa", "huella", "audio", "muestra", "otro"]
Confidence = Literal["baja", "media", "alta"]
CATEGORY_NOTE = "Categoría de conservación según la fuente indicada; el sistema no la evalúa."


def _opt(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


class SpeciesIn(BaseModel):
    nombre_cientifico: str = Field(min_length=3, max_length=160)
    nombre_comun: str = Field(default="", max_length=160)
    reino: str | None = Field(default=None, max_length=64)
    clase: str | None = Field(default=None, max_length=64)
    orden: str | None = Field(default=None, max_length=64)
    familia: str | None = Field(default=None, max_length=64)
    categoria_conservacion: str | None = None
    fuente_taxonomica: str = Field(min_length=3, max_length=256)
    notas: str = Field(default="", max_length=2000)

    @field_validator("nombre_cientifico", "fuente_taxonomica")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        v = service.normalize_name(v)
        if len(v) < 3:
            raise ValueError("Debe tener al menos 3 caracteres.")
        return v

    @field_validator("reino", "clase", "orden", "familia", "categoria_conservacion")
    @classmethod
    def _strip_opt(cls, v: str | None) -> str | None:
        return _opt(v)

    @field_validator("categoria_conservacion")
    @classmethod
    def _category(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.upper()
            if v not in CONSERVATION_CATEGORIES:
                raise ValueError(f"Categoría no válida. Use una de: {', '.join(CONSERVATION_CATEGORIES)}.")
        return v


class SpeciesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    nombre_cientifico: str
    nombre_comun: str
    reino: str | None
    clase: str | None
    orden: str | None
    familia: str | None
    categoria_conservacion: str | None
    fuente_taxonomica: str
    notas: str
    created_at: datetime
    aviso_categoria: str = CATEGORY_NOTE


class ObservationIn(BaseModel):
    species_id: str | None = None  # None = no identificada
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    fecha_observacion: datetime
    observador: str = Field(min_length=2, max_length=128)
    cantidad: int = Field(default=1, ge=1, le=1_000_000)
    metodo: Method
    photo_record_id: str | None = None
    confianza_identificacion: Confidence
    is_simulated: bool
    territory_id: str | None = None

    @field_validator("fecha_observacion")
    @classmethod
    def _not_future(cls, v: datetime) -> datetime:
        if service.to_utc(v) > datetime.now(UTC):
            raise ValueError("La fecha de observación no puede estar en el futuro.")
        return v

    @field_validator("observador")
    @classmethod
    def _observer(cls, v: str) -> str:
        v = service.normalize_name(v)
        if len(v) < 2:
            raise ValueError("Indique el observador.")
        return v


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    species_id: str | None
    nombre_cientifico: str | None = None
    nombre_comun: str = ""
    latitude: float
    longitude: float
    fecha_observacion: datetime
    observador: str
    cantidad: int
    metodo: str
    photo_record_id: str | None
    confianza_identificacion: str
    estado_validacion: str
    validation_note: str
    validated_at: datetime | None
    is_simulated: bool
    territory_id: str | None
    created_at: datetime


class ValidateIn(BaseModel):
    estado: Literal["validada", "descartada"]
    nota: str = Field(min_length=3, max_length=2000)


def _obs_out(o: Observation) -> ObservationOut:
    out = ObservationOut.model_validate(o)
    out.fecha_observacion = service.to_utc(o.fecha_observacion)
    if o.species:
        out.nombre_cientifico, out.nombre_comun = o.species.nombre_cientifico, o.species.nombre_comun
    return out


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        a, b, c, d = (float(x) for x in bbox.split(","))
    except ValueError as exc:
        raise HTTPException(422, "bbox debe ser 'minLon,minLat,maxLon,maxLat' con números.") from exc
    if not (-180 <= a <= c <= 180 and -90 <= b <= d <= 90):
        raise HTTPException(422, "bbox fuera de rango o con mínimos mayores que máximos.")
    return a, b, c, d


def _filtered(db: Session, species_id, desde, hasta, bbox, is_simulated, estado):
    stmt = select(Observation).order_by(Observation.fecha_observacion.desc(), Observation.id)
    return service.filter_observations(stmt, species_id=species_id, desde=desde, hasta=hasta,
                                       bbox=_parse_bbox(bbox), is_simulated=is_simulated, estado=estado)


# ---------- Especies ----------
@router.post("/species", response_model=SpeciesOut, status_code=201)
def create_species(body: SpeciesIn, user: User = Depends(require_role("analista")),
                   db: Session = Depends(get_db)) -> Species:
    if service.find_species_by_name(db, body.nombre_cientifico):
        raise HTTPException(409, "Ya existe una especie con ese nombre científico.")
    sp = Species(**body.model_dump(), created_by=user.id)
    db.add(sp)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Ya existe una especie con ese nombre científico.") from exc
    audit(db, "especie_creada", user_id=user.id, target_type="species", target_id=sp.id,
          details={"nombre_cientifico": sp.nombre_cientifico}, commit=False)
    db.commit()
    return sp


@router.get("/species", response_model=list[SpeciesOut])
def list_species(q: str | None = Query(None, max_length=100), limit: int = Query(100, ge=1, le=500),
                 offset: int = Query(0, ge=0), _: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[Species]:
    return service.search_species(db, q, limit, offset)


# ---------- Observaciones ----------
@router.post("/observations", response_model=ObservationOut, status_code=201)
def create_observation(body: ObservationIn, user: User = Depends(require_role("analista")),
                       db: Session = Depends(get_db)) -> ObservationOut:
    if body.species_id and db.get(Species, body.species_id) is None:
        raise HTTPException(422, "La especie indicada no existe.")
    if body.territory_id and db.get(Territory, body.territory_id) is None:
        raise HTTPException(422, "El territorio indicado no existe.")
    if body.photo_record_id and (msg := service.check_photo(db, body.photo_record_id)):
        raise HTTPException(422, msg)
    data = body.model_dump()
    data["fecha_observacion"] = service.to_utc(body.fecha_observacion)
    obs = Observation(**data, estado_validacion="no_validada", created_by=user.id)
    db.add(obs)
    db.flush()
    audit(db, "observacion_creada", user_id=user.id, target_type="observation", target_id=obs.id,
          details={"simulada": obs.is_simulated, "identificada": obs.species_id is not None}, commit=False)
    db.commit()
    db.refresh(obs)
    return _obs_out(obs)


@router.get("/observations/geojson")
def observations_geojson(species_id: str | None = None, desde: datetime | None = None,
                         hasta: datetime | None = None, bbox: str | None = None,
                         is_simulated: bool | None = None, estado: str | None = None,
                         incluir_descartadas: bool = False, _: User = Depends(get_current_user),
                         db: Session = Depends(get_db)) -> dict:
    """Capa para el mapa: un punto por observación; cada feature lleva is_simulated."""
    stmt = _filtered(db, species_id, desde, hasta, bbox, is_simulated, estado)
    if not incluir_descartadas and estado != "descartada":
        stmt = stmt.where(Observation.estado_validacion != "descartada")
    feats = [service.feature(o) for o in db.scalars(stmt.limit(5000))]
    return {"type": "FeatureCollection", "features": feats}


@router.get("/observations", response_model=list[ObservationOut])
def list_observations(species_id: str | None = None, desde: datetime | None = None,
                      hasta: datetime | None = None, bbox: str | None = None,
                      is_simulated: bool | None = None, estado: str | None = None,
                      limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                      _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ObservationOut]:
    stmt = _filtered(db, species_id, desde, hasta, bbox, is_simulated, estado)
    return [_obs_out(o) for o in db.scalars(stmt.limit(limit).offset(offset))]


@router.get("/observations/{observation_id}", response_model=ObservationOut)
def get_observation(observation_id: str, _: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> ObservationOut:
    obs = db.get(Observation, observation_id)
    if obs is None:
        raise HTTPException(404, "Observación no encontrada.")
    return _obs_out(obs)


@router.post("/observations/{observation_id}/validate", response_model=ObservationOut)
def validate_observation(observation_id: str, body: ValidateIn, user: User = Depends(require_role("admin")),
                         db: Session = Depends(get_db)) -> ObservationOut:
    obs = db.get(Observation, observation_id)
    if obs is None:
        raise HTTPException(404, "Observación no encontrada.")
    # Separación de funciones (igual que en los modelos de IA): quien registró no valida su propia observación.
    if obs.created_by == user.id:
        raise HTTPException(422, "Quien registró la observación no puede validarla: debe hacerlo otro administrador.")
    previous = obs.estado_validacion
    obs.estado_validacion = body.estado
    obs.validation_note = body.nota.strip()
    obs.validated_by = user.id
    obs.validated_at = utcnow()
    audit(db, "observacion_validada", user_id=user.id, target_type="observation", target_id=obs.id,
          details={"anterior": previous, "nuevo": body.estado, "nota": obs.validation_note,
                   "simulada": obs.is_simulated}, commit=False)
    db.commit()
    db.refresh(obs)
    return _obs_out(obs)


@router.get("/summary")
def get_summary(is_simulated: bool | None = None, _: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    return service.summary(db, is_simulated)
