from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import User
from app.modules.validation import engine

router = APIRouter(prefix="/api/validation", tags=["SCIENTIFIC VALIDATION ENGINE"])


class ExperimentIn(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    module_key: str = Field(pattern="^disasters$")
    question: str = Field(min_length=20, max_length=2000)
    protocol_text: str = Field(min_length=40, max_length=20000)
    criteria: dict
    test_region: list[float] | None = Field(default=None, min_length=4, max_length=4)


class EvaluationIn(BaseModel):
    run_id: str = Field(min_length=32, max_length=32)
    model_ref: str = Field(min_length=5, max_length=160)
    partition: str = Field(pattern="^(cv|test)$")


class DecisionIn(BaseModel):
    evaluation_id: str = Field(min_length=32, max_length=32)
    decision: str = Field(pattern="^(aprobar|rechazar)$")
    comment: str = Field(min_length=1, max_length=4000)


def _handle(fn):
    try:
        return fn()
    except engine.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except engine.SVEError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/experiments")
def experiments(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return engine.list_experiments(db)


@router.post("/experiments", status_code=201)
def create(body: ExperimentIn, user: User = Depends(require_role("analista")), db: Session = Depends(get_db)) -> dict:
    exp = _handle(lambda: engine.create_experiment(db, user, **body.model_dump()))
    return engine.to_dict(db, exp, detail=True)


@router.get("/experiments/{exp_id}")
def experiment(exp_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: engine.to_dict(db, engine.get_experiment(db, exp_id), detail=True))


@router.post("/experiments/{exp_id}/evaluations", status_code=201)
def evaluate(exp_id: str, body: EvaluationIn, user: User = Depends(require_role("analista")),
             db: Session = Depends(get_db)) -> dict:
    def go():
        exp = engine.get_experiment(db, exp_id)
        engine.add_evaluation(db, user, exp, **body.model_dump())
        return engine.to_dict(db, exp, detail=True)
    return _handle(go)


@router.post("/experiments/{exp_id}/decisions", status_code=201)
def decide(exp_id: str, body: DecisionIn, admin: User = Depends(require_role("admin")),
           db: Session = Depends(get_db)) -> dict:
    def go():
        exp = engine.get_experiment(db, exp_id)
        engine.approve(db, admin, exp, **body.model_dump())
        return engine.to_dict(db, exp, detail=True)
    return _handle(go)


@router.post("/experiments/{exp_id}/retire")
def retire(exp_id: str, admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)) -> dict:
    return _handle(lambda: engine.to_dict(db, engine.retire(db, admin, engine.get_experiment(db, exp_id))))
