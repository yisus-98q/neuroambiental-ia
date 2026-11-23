"""Biodiversidad: especies y observaciones georreferenciadas (sin especies precargadas)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.common import IdMixin, TimestampMixin

# Categorías tipo UICN. El sistema NO las evalúa: se muestran «según la fuente indicada».
CONSERVATION_CATEGORIES = ("EX", "EW", "CR", "EN", "VU", "NT", "LC", "DD", "NE")
METHODS = ("avistamiento", "camara_trampa", "huella", "audio", "muestra", "otro")
CONFIDENCE = ("baja", "media", "alta")
VALIDATION_STATES = ("no_validada", "validada", "descartada")


class Species(IdMixin, TimestampMixin, Base):
    __tablename__ = "species"
    __table_args__ = (UniqueConstraint("nombre_cientifico", name="uq_species_nombre_cientifico"),)

    nombre_cientifico: Mapped[str] = mapped_column(String(160), nullable=False)
    nombre_comun: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    reino: Mapped[str | None] = mapped_column(String(64))
    clase: Mapped[str | None] = mapped_column(String(64))
    orden: Mapped[str | None] = mapped_column(String(64))
    familia: Mapped[str | None] = mapped_column(String(64))
    categoria_conservacion: Mapped[str | None] = mapped_column(String(2))
    fuente_taxonomica: Mapped[str] = mapped_column(String(256), nullable=False)
    notas: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_species_created_by_users", ondelete="SET NULL"))


class Observation(IdMixin, TimestampMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint("cantidad >= 1", name="ck_observations_cantidad_min"),
        Index("ix_observations_species_id", "species_id"),
        Index("ix_observations_fecha_observacion", "fecha_observacion"),
        Index("ix_observations_estado_validacion", "estado_validacion"),
    )

    # NULL = «no identificada».
    species_id: Mapped[str | None] = mapped_column(
        ForeignKey("species.id", name="fk_observations_species_id_species", ondelete="SET NULL"))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_observacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observador: Mapped[str] = mapped_column(String(128), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metodo: Mapped[str] = mapped_column(String(16), nullable=False)
    photo_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("data_records.id", name="fk_observations_photo_record_id_data_records", ondelete="SET NULL"))
    # Declarada por el observador; el sistema no la verifica.
    confianza_identificacion: Mapped[str] = mapped_column(String(8), nullable=False)
    estado_validacion: Mapped[str] = mapped_column(String(16), nullable=False, default="no_validada",
                                                   server_default="no_validada")
    validation_note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    validated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_observations_validated_by_users", ondelete="SET NULL"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Regla innegociable: lo simulado siempre queda marcado.
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    territory_id: Mapped[str | None] = mapped_column(
        ForeignKey("territories.id", name="fk_observations_territory_id_territories", ondelete="SET NULL"))
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_observations_created_by_users", ondelete="SET NULL"))

    species: Mapped[Species | None] = relationship()
