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


@router.get("/overview")
def overview(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Centro de coordinación (Fase 7): estado VERIFICABLE de módulos, datos, modelos, validación y recursos.
    Todo sale de la base y del registro; nada se estima ni se rellena."""
    from sqlalchemy import func

    from app.core import hardware, jobs
    from app.models import AIModel, DataRecord, Run
    from app.models.validation import Experiment
    from app.modules.validation import engine as sve

    mods = registry.all()
    by_status: dict[str, int] = {}
    for m in mods:
        by_status[m.status.value] = by_status.get(m.status.value, 0) + 1
    data_rows = db.execute(select(DataRecord.data_type, DataRecord.is_simulated, func.count())
                           .group_by(DataRecord.data_type, DataRecord.is_simulated)).all()
    datasets: dict[str, dict] = {}
    for t, sim, n in data_rows:
        d = datasets.setdefault(t, {"reales": 0, "simulados": 0})
        d["simulados" if sim else "reales"] += n
    dup = db.execute(select(func.count()).select_from(
        select(DataRecord.sha256).where(DataRecord.sha256.isnot(None)).group_by(DataRecord.sha256)
        .having(func.count() > 1).subquery())).scalar() or 0
    models = dict(db.execute(select(AIModel.status, func.count()).group_by(AIModel.status)).all())
    exps = [sve.state(db, e) for e in db.scalars(select(Experiment))]
    exp_states = {s: exps.count(s) for s in set(exps)}
    runs = db.scalars(select(Run).order_by(Run.started_at.desc()).limit(12)).all()
    recent = [{"id": r.id, "tipo": r.run_type, "modulo": r.module_key, "estado": r.status,
               "inicio": r.started_at, "duracion_s": round((r.finished_at - r.started_at).total_seconds(), 1)
               if r.finished_at and r.started_at else None,
               "recursos": (r.result_summary or {}).get("recursos") if isinstance(r.result_summary, dict) else None}
              for r in runs]
    return {
        "modulos": {"total": len(mods), "por_estado": by_status},
        "datasets": {"por_tipo": datasets, "contenidos_duplicados_sha256": dup},
        "modelos": {"por_estado": models, "validados": models.get("validado", 0)},
        "validacion_cientifica": {"experimentos": len(exps), "por_estado": exp_states},
        "actividad_reciente": recent,
        "recursos": {**hardware.snapshot(), "trabajo_en_curso": jobs.current()},
        "validacion_externa": _external_summary(db),
        "nota": "Un módulo «registrado» no es un módulo operativo: el estado se calcula con sus capacidades implementadas.",
    }



def _external_summary(db: Session) -> dict | None:
    """Última evaluación externa: fecha, zona, datasets, estados, métricas e incertidumbre (misión 2.1)."""
    from app.models import Run
    r = db.scalars(select(Run).where(Run.run_type == "validacion_externa", Run.status == "ok")
                   .order_by(Run.started_at.desc()).limit(1)).first()
    if r is None:
        return None
    res = r.result_summary or {}
    hist = db.scalars(select(Run).where(Run.run_type.in_(("validacion_externa", "validacion_susceptibilidad")))
                      .order_by(Run.started_at.desc()).limit(20)).all()
    grupos = {}
    for g, v in (res.get("grupos") or {}).items():
        franja = v.get("franja") or {}
        grupos[g] = {"eventos_externos": v.get("n_eventos_externos"),
                     "modelos": {n: {"estado": st["estado"], "motivo": st.get("motivo"),
                                     "auc": (franja.get(n) or {}).get("auc_sorteos", {}).get("media"),
                                     "ic95": (franja.get(n) or {}).get("auc_ic95_bloques")}
                                 for n, st in (v.get("estados") or {}).items()}}
    return {"run_id": r.id, "fecha": r.finished_at, "zona": res.get("zona_externa"), "datasets": r.parameters,
            "version_codigo": "posterior a la etiqueta mision-2.0-congelada", "grupos": grupos,
            "limitaciones": ["Una sola zona externa; mismo estudio y autores que el entrenamiento.",
                             "Pseudo-ausencias; IC por bootstrap de bloques; ningún modelo validado."],
            "historial": [{"id": h.id, "tipo": h.run_type, "fecha": h.started_at} for h in hist]}
