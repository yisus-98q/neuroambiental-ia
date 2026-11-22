"""NEUROVOICE IA (fase 1): respuestas en español construidas SOLO con datos reales del sistema."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, DataRecord
from app.neurocore.registry import Interpretation, ModuleRegistry, interpret


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def build_reply(db: Session, text: str, reg: ModuleRegistry) -> tuple[str, Interpretation]:
    it = interpret(text, reg)
    if it.intent == "estado_modulos":
        parts = [f"- {m.name}: {m.status.value}" for m in reg.all()]
        return "Estado actual de los módulos (derivado de sus capacidades implementadas):\n" + "\n".join(parts), it
    if it.intent == "desconocida":
        return ("No reconocí la solicitud. Fase 1: entiendo palabras clave en español sobre alertas, datos, "
                "módulos (por ejemplo «estado de los módulos», «cuántas alertas hay», «cargar datos CSV»). "
                "Aún no uso un modelo de lenguaje."), it

    module = reg.get(it.module_key or "")
    assert module is not None
    lines = [f"Tu consulta corresponde al módulo «{module.name}» (estado: {module.status.value})."]
    if it.module_key == "alerts":
        total = _count(db, select(func.count()).select_from(Alert))
        unvalidated = _count(db, select(func.count()).where(Alert.validation_status == "no_validada"))
        high = _count(db, select(func.count()).where(Alert.level == "alto"))
        lines.append(f"Hay {total} alerta(s) experimental(es) registradas; {high} de nivel alto y "
                     f"{unvalidated} sin validar. Ninguna es una emergencia oficial.")
    elif it.module_key == "neurodata":
        total = _count(db, select(func.count()).select_from(DataRecord))
        sim = _count(db, select(func.count()).where(DataRecord.is_simulated.is_(True)))
        lines.append(f"NEURODATA contiene {total} registro(s): {total - sim} real(es) y {sim} simulado(s).")
    implemented = [c.description for c in module.capabilities if c.implemented]
    pending = [c.description for c in module.capabilities if not c.implemented]
    if implemented:
        lines.append("Disponible ahora: " + "; ".join(implemented) + ".")
    if pending:
        lines.append("Aún no implementado: " + "; ".join(pending) + ".")
    for lim in module.limitations:
        lines.append(f"Limitación: {lim}")
    return "\n".join(lines), it
