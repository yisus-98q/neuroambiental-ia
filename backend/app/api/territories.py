from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import Territory, User
from app.neurodata.validators import validate_geojson
from app.schemas import TerritoryIn, TerritoryOut

router = APIRouter(prefix="/api/territories", tags=["territorios"])


@router.get("", response_model=list[TerritoryOut])
def list_territories(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Territory]:
    return list(db.scalars(select(Territory).order_by(Territory.name)))


@router.post("", response_model=TerritoryOut, status_code=201)
def create_territory(body: TerritoryIn, user: User = Depends(require_role("analista")),
                     db: Session = Depends(get_db)) -> Territory:
    if body.geometry is not None:
        result = validate_geojson(json.dumps(body.geometry).encode())
        if not result.valid:
            raise HTTPException(422, {"message": "Geometría inválida.", "errors": result.messages})
    territory = Territory(**body.model_dump())
    db.add(territory)
    db.flush()
    audit(db, "crear_territorio", user_id=user.id, target_type="territory", target_id=territory.id, commit=False)
    db.commit()
    return territory
