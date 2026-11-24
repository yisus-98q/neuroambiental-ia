from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.lazy import lazy
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import User

# Carga diferida: scikit-learn/scipy/rasterio solo al validar.
service = lazy("app.modules.disasters.service")
inventory = lazy("app.modules.disasters.inventory")
validation = lazy("app.modules.disasters.validation")
dem = lazy("app.modules.neuro3d.dem")

router = APIRouter(prefix="/api/disasters", tags=["NEURODISASTER"])
MAX_SPAN = 2.5  # grados: un departamento como Áncash cabe; evita descargas nacionales


class InventoryIn(BaseModel):
    bbox: list[float] = Field(min_length=4, max_length=4)

    @field_validator("bbox")
    @classmethod
    def _bbox(cls, v):
        a, b, c, d = v
        if not (-180 <= a < c <= 180 and -90 <= b < d <= 90):
            raise ValueError("bbox inválido: [minLon, minLat, maxLon, maxLat].")
        if c - a > MAX_SPAN or d - b > MAX_SPAN:
            raise ValueError(f"Área máxima {MAX_SPAN}° por lado.")
        return v


class ValidateIn(BaseModel):
    dem_id: str = Field(min_length=32, max_length=32)
    inventory_id: str = Field(min_length=32, max_length=32)
    ratio: int = Field(default=3, ge=1, le=10)
    min_dist_m: float = Field(default=300, ge=50, le=5000)
    blocks: int = Field(default=4, ge=2, le=8)
    seed: int = Field(default=42, ge=0, le=10_000)
    n_seeds: int = Field(default=5, ge=1, le=10)
    buffer_m: float = Field(default=500, ge=0, le=5000)


def _handle(fn):
    try:
        return fn()
    except jobs.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except (validation.ValidationError, dem.DemError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except inventory.InventoryError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/inventory/import", status_code=201)
def import_inventory(body: InventoryIn, user: User = Depends(require_role("analista")),
                     db: Session = Depends(get_db)) -> dict:
    rec = _handle(lambda: service.import_inventory(db, user, body.bbox))
    return {"id": rec.id, "title": rec.title, "bbox": rec.bbox, "is_simulated": rec.is_simulated,
            "provenance": rec.provenance, "source": rec.source.name, "license": rec.source.license,
            "eventos": rec.extra.get("features"), "tipos_peligro": rec.extra.get("tipos_peligro")}


@router.post("/susceptibility/validate", status_code=201)
def validate(body: ValidateIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: service.validate(db, user, dem_id=body.dem_id, inventory_id=body.inventory_id,
                                            ratio=body.ratio, min_dist_m=body.min_dist_m, blocks=body.blocks,
                                            seed=body.seed, n_seeds=body.n_seeds, buffer_m=body.buffer_m))


@router.get("/runs")
def runs(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_runs(db)


@router.get("/inventories")
def inventories(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_inventories(db)
