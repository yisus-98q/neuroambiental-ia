from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import AIModel, Run, User
from app.neurocore.registry import registry
from app.schemas import AIModelIn, AIModelOut

router = APIRouter(prefix="/api/neurotraining", tags=["NEUROTRAINING"])


@router.get("/models", response_model=list[AIModelOut])
def list_models(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AIModel]:
    return list(db.scalars(select(AIModel).order_by(AIModel.created_at.desc())))


@router.post("/models", response_model=AIModelOut, status_code=201)
def register_model(body: AIModelIn, user: User = Depends(require_role("analista")),
                   db: Session = Depends(get_db)) -> AIModel:
    if registry.get(body.module_key) is None:
        raise HTTPException(422, f"Módulo desconocido: {body.module_key}")
    # Un modelo nuevo SIEMPRE nace como 'planificado'. No se puede declarar entrenado por API.
    model = AIModel(**body.model_dump(), status="planificado")
    db.add(model)
    db.flush()
    audit(db, "registrar_modelo", user_id=user.id, target_type="ai_model", target_id=model.id, commit=False)
    db.commit()
    return model


@router.get("/runs")
def list_runs(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Run).order_by(Run.started_at.desc()).limit(100))
    return [{"id": r.id, "run_type": r.run_type, "module_key": r.module_key, "status": r.status,
             "started_at": r.started_at, "finished_at": r.finished_at} for r in rows]
