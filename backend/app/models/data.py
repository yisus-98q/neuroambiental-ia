"""NEURODATA: datos recibidos, sensores, mediciones y documentos."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.common import IdMixin, TimestampMixin, utcnow
from app.models.territory import Source


class DataRecord(IdMixin, Base):
    """Cada dato que entra al sistema, con procedencia completa."""

    __tablename__ = "data_records"
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    # csv, geojson, imagen, documento, medicion_manual
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    territory_id: Mapped[str | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    bbox: Mapped[list | None] = mapped_column(JSON)  # [minLon, minLat, maxLon, maxLat]
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="")
    value: Mapped[float | None] = mapped_column(Float)
    file_format: Mapped[str] = mapped_column(String(32), default="")
    # pendiente, valido, invalido
    validation_status: Mapped[str] = mapped_column(String(16), default="pendiente", nullable=False)
    validation_messages: Mapped[list] = mapped_column(JSON, default=list)
    quality: Mapped[str] = mapped_column(String(16), default="sin_evaluar")  # sin_evaluar, baja, media, alta
    provenance: Mapped[str] = mapped_column(Text, default="")
    # Regla innegociable: los datos simulados siempre quedan marcados.
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512))  # relativo a uploads_dir
    file_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    source: Mapped[Source] = relationship()


class Sensor(IdMixin, TimestampMixin, Base):
    __tablename__ = "sensors"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # gps, inclinometro, piezometro, pluviometro, estacion_meteorologica, otro
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    territory_id: Mapped[str | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Measurement(IdMixin, Base):
    __tablename__ = "measurements"
    sensor_id: Mapped[str | None] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    data_record_id: Mapped[str | None] = mapped_column(ForeignKey("data_records.id", ondelete="CASCADE"))
    variable: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    data_record_id: Mapped[str] = mapped_column(ForeignKey("data_records.id", ondelete="CASCADE"))
    # plano, informe_tecnico, estudio, otro
    category: Mapped[str] = mapped_column(String(32), default="otro")
    module_key: Mapped[str] = mapped_column(String(32), default="construction")
    notes: Mapped[str] = mapped_column(Text, default="")
