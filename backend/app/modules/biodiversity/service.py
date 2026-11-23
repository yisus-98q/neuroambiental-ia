"""Lógica de biodiversidad: consultas, resumen y capa GeoJSON. Sin análisis ni modelos."""
from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import DataRecord
from app.models.biodiversity import Observation, Species

SUMMARY_CAP = 50_000
RICHNESS_WARNING = (
    "La riqueza es el número de especies distintas observadas y depende del esfuerzo de muestreo "
    "(cuánto, dónde y cuándo se buscó): no es un índice de biodiversidad ni permite comparar sitios por sí sola."
)


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def find_species_by_name(db: Session, name: str) -> Species | None:
    return db.scalar(select(Species).where(func.lower(Species.nombre_cientifico) == name.lower()))


def search_species(db: Session, q: str | None, limit: int, offset: int) -> list[Species]:
    stmt = select(Species).order_by(Species.nombre_cientifico)
    if q and q.strip():
        like = "%" + q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(func.lower(Species.nombre_cientifico).like(like, escape="\\")
                          | func.lower(Species.nombre_comun).like(like, escape="\\"))
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def check_photo(db: Session, record_id: str) -> str | None:
    """Devuelve un mensaje de error si el registro no existe o no es una imagen válida de NEURODATA."""
    rec = db.get(DataRecord, record_id)
    if rec is None:
        return "El registro de foto no existe en NEURODATA."
    if rec.data_type != "imagen" or rec.validation_status != "valido":
        return "El registro indicado no es una imagen válida de NEURODATA."
    return None


def filter_observations(stmt: Select, *, species_id: str | None = None, desde: datetime | None = None,
                        hasta: datetime | None = None, bbox: tuple[float, float, float, float] | None = None,
                        is_simulated: bool | None = None, estado: str | None = None) -> Select:
    if species_id:
        stmt = stmt.where(Observation.species_id == species_id)
    if desde:
        stmt = stmt.where(Observation.fecha_observacion >= to_utc(desde))
    if hasta:
        stmt = stmt.where(Observation.fecha_observacion <= to_utc(hasta))
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        stmt = stmt.where(Observation.longitude.between(min_lon, max_lon),
                          Observation.latitude.between(min_lat, max_lat))
    if is_simulated is not None:
        stmt = stmt.where(Observation.is_simulated.is_(is_simulated))
    if estado:
        stmt = stmt.where(Observation.estado_validacion == estado)
    return stmt


def summary(db: Session, is_simulated: bool | None = None) -> dict:
    stmt = filter_observations(
        select(Observation.species_id, Observation.fecha_observacion, Observation.estado_validacion,
               Observation.cantidad, Observation.is_simulated).limit(SUMMARY_CAP), is_simulated=is_simulated)
    rows = db.execute(stmt).all()
    names = {s.id: s.nombre_cientifico for s in db.scalars(select(Species))}
    by_species: Counter = Counter()
    individuals: Counter = Counter()
    by_month: Counter = Counter()
    by_state: Counter = Counter()
    distinct: set[str] = set()
    distinct_real: set[str] = set()
    for sid, fecha, estado, cantidad, sim in rows:
        key = sid or "__sin_identificar__"
        by_species[key] += 1
        individuals[key] += cantidad
        by_month[f"{fecha:%Y-%m}"] += 1
        by_state[estado] += 1
        if sid and estado != "descartada":
            distinct.add(sid)
            if not sim:
                distinct_real.add(sid)
    return {
        "total_observaciones": len(rows),
        "truncado": len(rows) >= SUMMARY_CAP,
        "por_especie": [
            {"species_id": None if k == "__sin_identificar__" else k,
             "nombre_cientifico": "No identificada" if k == "__sin_identificar__" else names.get(k, "?"),
             "observaciones": n, "individuos": individuals[k]}
            for k, n in by_species.most_common()],
        "por_mes": [{"mes": m, "observaciones": by_month[m]} for m in sorted(by_month)],
        "por_estado": {s: by_state.get(s, 0) for s in ("no_validada", "validada", "descartada")},
        "riqueza_especies": len(distinct),
        "riqueza_especies_solo_reales": len(distinct_real),
        "riqueza_nota": "Excluye observaciones descartadas y no identificadas. " + RICHNESS_WARNING,
        "aviso": RICHNESS_WARNING,
    }


def feature(o: Observation) -> dict:
    sp = o.species
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [o.longitude, o.latitude]},
        "properties": {
            "observation_id": o.id,
            "species_id": o.species_id,
            "nombre_cientifico": sp.nombre_cientifico if sp else None,
            "nombre_comun": sp.nombre_comun if sp else "",
            "identificada": sp is not None,
            "fecha_observacion": to_utc(o.fecha_observacion).isoformat(),
            "cantidad": o.cantidad,
            "metodo": o.metodo,
            "confianza_identificacion": o.confianza_identificacion,
            "estado_validacion": o.estado_validacion,
            "is_simulated": o.is_simulated,
            "kind": "observacion_biodiversidad",
        },
    }
