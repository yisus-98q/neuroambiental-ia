from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database.session import get_db
from app.models import Alert, AuditLog, DataRecord, Report, Source, User
from app.neurocore.registry import registry

router = APIRouter(prefix="/api", tags=["sistema"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 - se informa como estado, no se oculta
        db_ok = False
    return {"status": "ok" if db_ok else "degradado", "database": "ok" if db_ok else "error",
            "app": settings.app_name, "version": settings.version}


@router.get("/reports")
def list_reports(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Informes generados por cualquier módulo (Fase 1: informes de alertas)."""
    rows = db.scalars(select(Report).order_by(Report.created_at.desc()).limit(100))
    return [{"id": r.id, "title": r.title, "module_key": r.module_key, "created_at": r.created_at,
             "content_md": r.content_md} for r in rows]


@router.get("/dashboard")
def dashboard(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Resumen del Home. Todas las cifras salen de la base de datos; nada se inventa."""
    by_level = dict(db.execute(select(Alert.level, func.count()).group_by(Alert.level)).all())
    by_status = dict(db.execute(select(Alert.validation_status, func.count()).group_by(Alert.validation_status)).all())
    records_by_type = dict(db.execute(select(DataRecord.data_type, func.count()).group_by(DataRecord.data_type)).all())
    simulated = db.scalar(select(func.count()).where(DataRecord.is_simulated.is_(True))) or 0
    total_records = sum(records_by_type.values())
    recent = db.scalars(select(AuditLog).order_by(AuditLog.at.desc()).limit(10)).all()
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    modules = [m.public() for m in registry.all()]
    return {
        "alerts": {"total": sum(by_level.values()), "by_level": by_level, "by_status": by_status},
        "records": {"total": total_records, "by_type": records_by_type,
                    "simulated": simulated, "real": total_records - simulated},
        "recent_activity": [
            {"at": a.at, "action": a.action, "target_type": a.target_type, "success": a.success} for a in recent
        ],
        "sources": [{"name": s.name, "kind": s.kind, "license": s.license} for s in sources],
        "modules": [{"key": m["key"], "name": m["name"], "status": m["status"]} for m in modules],
        "processing": {"queued_jobs": 0, "note": "Fase 1: no existen procesos en segundo plano."},
    }
