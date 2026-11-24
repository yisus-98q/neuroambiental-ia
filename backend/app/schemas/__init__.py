"""Esquemas Pydantic: validación de entrada en la frontera del sistema."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Latitude = Field(default=None, ge=-90, le=90)
Longitude = Field(default=None, ge=-180, le=180)


class _Geo(BaseModel):
    latitude: float | None = Latitude
    longitude: float | None = Longitude

    @model_validator(mode="after")
    def _both_or_none(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitud y longitud deben indicarse juntas.")
        return self


# ---------- Autenticación ----------
class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    full_name: str
    role_key: str
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(default="", max_length=128)
    password: str = Field(min_length=10, max_length=256)
    role_key: Literal["admin", "analista", "lector"] = "lector"


# ---------- NEURODATA ----------
class ManualRecordIn(_Geo):
    title: str = Field(min_length=1, max_length=256)
    variable: str = Field(default="", max_length=64)
    value: float | None = None
    unit: str = Field(default="", max_length=32)
    observed_at: datetime | None = None
    source_name: str = Field(min_length=1, max_length=128)
    provenance: str = Field(default="", max_length=2000)
    is_simulated: bool
    quality: Literal["sin_evaluar", "baja", "media", "alta"] = "sin_evaluar"
    territory_id: str | None = None

    @field_validator("observed_at")
    @classmethod
    def _not_future(cls, v: datetime | None):
        if v is not None:
            from datetime import UTC
            aware = v if v.tzinfo else v.replace(tzinfo=UTC)
            if aware > datetime.now(UTC):
                raise ValueError("La fecha de observación no puede estar en el futuro.")
        return v


class DataRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_type: str
    title: str
    source_name: str = ""
    latitude: float | None
    longitude: float | None
    bbox: list[float] | None
    observed_at: datetime | None
    received_at: datetime
    unit: str
    value: float | None
    file_format: str
    validation_status: str
    validation_messages: list
    quality: str
    provenance: str
    is_simulated: bool
    file_size: int | None
    sha256: str | None
    extra: dict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    kind: str
    url: str
    license: str
    terms_reviewed: bool
    notes: str


# ---------- Alertas ----------
AlertLevel = Literal["bajo", "medio", "alto"]
ValidationState = Literal["no_validada", "en_revision", "validada", "descartada"]


class AlertIn(_Geo):
    title: str = Field(min_length=3, max_length=256)
    description: str = Field(default="", max_length=5000)
    module_key: str = Field(default="alerts", max_length=32)
    level: AlertLevel
    evidence: str = Field(default="", max_length=5000)
    source_name: str = Field(min_length=1, max_length=128)
    observed_at: datetime | None = None
    uncertainty: str = Field(min_length=3, max_length=2000)
    is_simulated: bool


class FollowupIn(BaseModel):
    note: str = Field(min_length=3, max_length=5000)
    new_status: ValidationState | None = None


class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    note: str
    new_status: str | None
    created_at: datetime
    created_by: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    module_key: str
    level: str
    alert_kind: str
    latitude: float | None
    longitude: float | None
    evidence: str
    source_name: str
    observed_at: datetime | None
    uncertainty: str
    validation_status: str
    is_simulated: bool
    created_at: datetime
    followups: list[FollowupOut] = []


class EventIn(_Geo):
    event_type: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=3, max_length=256)
    description: str = Field(default="", max_length=5000)
    occurred_at: datetime | None = None
    source_name: str = Field(min_length=1, max_length=128)
    is_simulated: bool


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_type: str
    title: str
    description: str
    latitude: float | None
    longitude: float | None
    occurred_at: datetime | None
    source_name: str
    is_simulated: bool
    created_at: datetime


# ---------- NEUROTRAINING ----------
class AIModelIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    module_key: str = Field(min_length=2, max_length=32)
    algorithm: str = Field(default="", max_length=64)
    dataset_description: str = Field(default="", max_length=5000)


class AIModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    module_key: str
    algorithm: str
    version: str
    status: str
    metrics: dict
    dataset_description: str
    created_at: datetime
    task: str | None = None
    target: str | None = None
    features: list = []
    dataset_record_id: str | None = None
    trained_with_simulated: bool = False
    artifact_sha256: str | None = None
    trained_at: datetime | None = None
    validation_evidence: str = ""


# ---------- NEUROVOICE ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    # Módulo que el usuario está viendo (contexto de la pantalla); solo se usa si existe en NEUROCORE.
    context_module: str | None = Field(default=None, max_length=32, pattern="^[a-z0-9_]+$")


class ChatOut(BaseModel):
    conversation_id: str
    reply: str
    intent: str
    module_key: str | None
    method: str


# ---------- Territorios ----------
class TerritoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    level: str = Field(default="area_personalizada", max_length=32)
    country_code: str = Field(default="PE", min_length=2, max_length=2)
    geometry: dict | None = None
    description: str = Field(default="", max_length=2000)


class TerritoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    level: str
    country_code: str
    geometry: dict | None
    description: str
