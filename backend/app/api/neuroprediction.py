from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.modules.neuroprediction import ledger

router = APIRouter(prefix="/api/neuroprediction", tags=["NEURO PREDICTION ENGINE"])


def _check(tipo: str) -> None:
    if tipo not in ledger.KINDS:
        raise HTTPException(422, f"Tipo desconocido. Tipos válidos: {', '.join(ledger.KINDS)}.")


@router.get("/kinds")
def kinds(_: User = Depends(get_current_user)) -> list[dict]:
    return [{"tipo": k, "etiqueta": v["etiqueta"], "definicion": v["definicion"], "regla": v["regla"],
             "verificado": v["verificado"], "limitaciones": v["limitaciones"]} for k, v in ledger.KINDS.items()]


@router.get("/catalog")
def catalog(tipo: str | None = None, limit: int = Query(50, ge=1, le=ledger.MAX_LIMIT), offset: int = Query(0, ge=0),
            _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if tipo:
        _check(tipo)
    return ledger.catalog(db, tipo, limit, offset)


@router.get("/catalog/{tipo}/{item_id}")
def catalog_item(tipo: str, item_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _check(tipo)
    item = ledger.detail(db, tipo, item_id)
    if item is None:
        raise HTTPException(404, "Elemento no encontrado en ese tipo.")
    return item
