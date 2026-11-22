"""Territorios, coordenadas y fuentes de datos."""
from __future__ import annotations

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.common import IdMixin, TimestampMixin


class Territory(IdMixin, TimestampMixin, Base):
    __tablename__ = "territories"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="PE", nullable=False)
    # pais, region, provincia, distrito, cuenca, area_personalizada
    level: Mapped[str] = mapped_column(String(32), default="area_personalizada")
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    # Geometría GeoJSON (EPSG:4326). En PostGIS pasará a columna geometry.
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Coordinate(IdMixin, TimestampMixin, Base):
    __tablename__ = "coordinates"
    territory_id: Mapped[str | None] = mapped_column(ForeignKey("territories.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(128), default="")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    crs: Mapped[str] = mapped_column(String(16), default="EPSG:4326", nullable=False)


class Source(IdMixin, TimestampMixin, Base):
    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # carga_manual, archivo, sensor, satelite, servicio_publico, muestra_de_prueba
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(512), default="")
    license: Mapped[str] = mapped_column(String(128), default="desconocida")
    terms_reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
