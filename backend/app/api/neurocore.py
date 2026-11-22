from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import AuditLog, User
from app.neurocore.registry import interpret, registry

router = APIRouter(prefix="/api/neurocore", tags=["NEUROCORE IA"])

CORE_INFO = {
    "key": "neurocore",
    "name": "NEUROCORE IA",
    "version": "0.1.0",
    "status": "operativo",
    "description": "Coordinador central: registro de módulos, interpretación de solicitudes y auditoría.",
    "interpreter": "reglas_palabras_clave (sin modelo de lenguaje)",
}


class InterpretIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.get("")
def core_info() -> dict:
    return {**CORE_INFO, "modules_registered": len(registry.all())}


@router.get("/modules")
def list_modules() -> list[dict]:
    return [m.public() for m in registry.all()]


@router.get("/modules/{key}")
def get_module(key: str) -> dict:
    module = registry.get(key)
    if module is None:
        raise HTTPException(404, "Módulo no registrado.")
    return module.public()


@router.post("/interpret")
def interpret_request(body: InterpretIn, _: User = Depends(get_current_user)) -> dict:
    it = interpret(body.text)
    module = registry.get(it.module_key) if it.module_key else None
    return {"intent": it.intent, "module_key": it.module_key, "matched_keywords": it.matched_keywords,
            "method": it.method, "module_status": module.status.value if module else None}


@router.get("/operations")
def operations(limit: int = 50, _: User = Depends(require_role("analista")),
               db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.at.desc()).limit(min(max(limit, 1), 200)))
    return [{"id": a.id, "at": a.at, "user_id": a.user_id, "action": a.action, "target_type": a.target_type,
             "target_id": a.target_id, "success": a.success, "details": a.details} for a in rows]
