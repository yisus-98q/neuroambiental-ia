from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.audit import audit
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import AIModel, Prediction, Run, User
from app.modules.neurotraining import service, trainer
from app.neurocore.registry import registry
from app.schemas import AIModelIn, AIModelOut

router = APIRouter(prefix="/api/neurotraining", tags=["NEUROTRAINING"])


class TrainIn(BaseModel):
    dataset_record_id: str = Field(min_length=32, max_length=32)
    task: Literal["clasificacion", "regresion"]
    target: str = Field(min_length=1, max_length=128)
    features: list[str] = Field(min_length=1, max_length=trainer.MAX_FEATURES)
    algorithm: Literal["random_forest", "regresion_logistica", "ridge"]


class ValidateIn(BaseModel):
    evidence: str = Field(min_length=1, max_length=5000)


class PredictIn(BaseModel):
    dataset_record_id: str = Field(min_length=32, max_length=32)


def _get(db: Session, model_id: str) -> AIModel:
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(404, "Modelo no encontrado.")
    return m


def _handle(fn):
    try:
        return fn()
    except jobs.Busy as exc:
        raise HTTPException(409, str(exc)) from exc
    except (trainer.TrainingError, service.ModelStateError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/models", response_model=list[AIModelOut])
def list_models(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AIModel]:
    return list(db.scalars(select(AIModel).order_by(AIModel.created_at.desc())))


@router.get("/models/{model_id}", response_model=AIModelOut)
def get_model(model_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AIModel:
    return _get(db, model_id)


@router.post("/models", response_model=AIModelOut, status_code=201)
def register_model(body: AIModelIn, user: User = Depends(require_role("analista")),
                   db: Session = Depends(get_db)) -> AIModel:
    if registry.get(body.module_key) is None:
        raise HTTPException(422, f"Módulo desconocido: {body.module_key}")
    # Un modelo nuevo SIEMPRE nace como 'planificado'. Solo el entrenamiento real lo cambia.
    model = AIModel(**body.model_dump(), status="planificado")
    db.add(model)
    db.flush()
    audit(db, "registrar_modelo", user_id=user.id, target_type="ai_model", target_id=model.id, commit=False)
    db.commit()
    return model


@router.post("/models/{model_id}/train", response_model=AIModelOut)
def train(model_id: str, body: TrainIn, user: User = Depends(require_role("analista")),
          db: Session = Depends(get_db)) -> AIModel:
    model = _get(db, model_id)
    return _handle(lambda: service.train_model(db, user, model, dataset_id=body.dataset_record_id, task=body.task,
                                               target=body.target, features=body.features,
                                               algorithm=body.algorithm))


@router.post("/models/{model_id}/validate", response_model=AIModelOut)
def validate(model_id: str, body: ValidateIn, admin: User = Depends(require_role("admin")),
             db: Session = Depends(get_db)) -> AIModel:
    model = _get(db, model_id)
    return _handle(lambda: service.validate_model(db, admin, model, body.evidence))


@router.post("/models/{model_id}/retire", response_model=AIModelOut)
def retire(model_id: str, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> AIModel:
    return service.retire_model(db, admin, _get(db, model_id))


@router.post("/models/{model_id}/predict")
def predict(model_id: str, body: PredictIn, user: User = Depends(require_role("analista")),
            db: Session = Depends(get_db)) -> dict:
    model = _get(db, model_id)
    return _handle(lambda: service.predict(db, user, model, body.dataset_record_id))


@router.get("/predictions")
def predictions(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(50))
    return [{"id": p.id, "model_id": p.model_id, "target": p.target, "created_at": p.created_at,
             "is_validated": p.is_validated, "uncertainty": p.uncertainty,
             "summary": p.value.get("summary"), "n": p.value.get("n")} for p in rows]


@router.get("/runs")
def list_runs(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Run).order_by(Run.started_at.desc()).limit(100))
    return [{"id": r.id, "run_type": r.run_type, "module_key": r.module_key, "status": r.status,
             "started_at": r.started_at, "finished_at": r.finished_at, "result_summary": r.result_summary}
            for r in rows]
