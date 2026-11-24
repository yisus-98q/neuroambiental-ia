"""NEUROVOICE IA: respuestas en español construidas SOLO con datos reales del sistema.

Consulta a NEUROCORE (registro de módulos) y a las tablas reales. Nunca inventa cifras: si no hay datos,
lo dice. Las simulaciones se nombran siempre como simulaciones y las estimaciones como experimentales.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AIModel, Alert, DataRecord, Run
from app.neurocore.registry import Interpretation, ModuleRegistry, interpret, normalize

SCENARIO_TYPES = ("raster_escenario",)  # resultados hipotéticos calculados, nunca observaciones

# Palabras que piden seguir con el tema anterior («explícame más», «y eso qué significa»).
_FOLLOW_UP = {"explica", "explicame", "explicar", "mas", "detalle", "detalles", "eso", "significa", "continua", "sigue"}


def _count(db: Session, stmt) -> int:
    return db.scalar(stmt) or 0


def _latest(db: Session, data_type: str) -> DataRecord | None:
    return db.scalar(select(DataRecord).where(DataRecord.data_type == data_type)
                     .order_by(DataRecord.received_at.desc()).limit(1))


def _scenario_lines(db: Session) -> list[str]:
    lines = []
    dem = _latest(db, "raster_dem")
    if dem is None:
        return ["Aún no hay ningún terreno (DEM) descargado en NEURO 3D LAB."]
    elev = (dem.extra or {}).get("elevation", {})
    lines.append(f"Último terreno real: {dem.title}; elevación observada entre {elev.get('min')} y {elev.get('max')} m.")
    sc = _latest(db, "raster_escenario")
    if sc is None:
        lines.append("No hay escenarios calculados todavía.")
        return lines
    ex = sc.extra or {}
    st = ex.get("stats", {})
    lines.append(f"SIMULACIÓN más reciente ({ex.get('kind', 'escenario')}): «{sc.title}». Es un escenario hipotético, "
                 "no una predicción.")
    if ex.get("kind") == "susceptibilidad" and st.get("classes"):
        parts = [f"{c['label']} {c['pct']} %" for c in st["classes"]]
        lines.append("Clases del índice heurístico: " + ", ".join(parts) + ".")
    elif ex.get("kind") == "inundacion_demostrativa":
        lines.append(f"Lámina de agua local de {st.get('rise_m')} m: {st.get('flooded_km2')} km², profundidad máxima "
                     f"{st.get('max_depth_m')} m.")
    if ex.get("disclaimer"):
        lines.append(ex["disclaimer"])
    return lines


def _disaster_lines(db: Session) -> list[str]:
    run = db.scalar(select(Run).where(Run.module_key == "disasters", Run.run_type == "validacion_susceptibilidad",
                                      Run.status == "ok").order_by(Run.started_at.desc()).limit(1))
    if run is None or not run.result_summary:
        return ["Aún no hay ninguna validación con eventos reales. Importe el inventario de INGEMMET y valide en "
                "NEURODISASTER."]
    r = run.result_summary
    libre, aj = r.get("ausencias_libres", {}), r.get("ausencias_mismo_rango_elevacion", {})
    lr = (aj.get("regresion_logistica") or {}).get("espacial") or {}
    lines = [f"Última validación con eventos REALES de INGEMMET: {libre.get('n_presencias')} eventos frente a "
             f"{libre.get('n_ausencias')} pseudo-ausencias.",
             f"Índice heurístico de pendiente: AUC {_dec(libre.get('auc_heuristico_pendiente'))} (0,5 es azar).",
             f"Pendiente + elevación con el sesgo de altura corregido, validación espacial: AUC {_dec(lr.get('auc_mean'))}"
             f" ± {_dec(lr.get('auc_sd'))}."]
    lines += list(r.get("conclusion_automatica") or [])[:3]
    lines.append("Ningún modelo de susceptibilidad está validado: es una evaluación experimental.")
    return lines


def _dec(v) -> str:
    return "—" if v is None else f"{float(v):.2f}".replace(".", ",")


def _prediction_lines(db: Session) -> list[str]:
    from app.modules.neuroprediction import ledger  # import local: evita ciclos al registrar módulos

    totals = {k: ledger.count_kind(db, k) for k in ledger.KINDS}
    nice = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in totals.items())
    lines = [f"Catálogo de resultados separado por tipo — {nice}."]
    if totals.get("prediccion", 0) == 0:
        lines.append("No hay predicciones validadas: todo lo que estima un modelo es experimental.")
    return lines


def _environment_lines(db: Session) -> list[str]:
    nd = _latest(db, "raster_ndvi")
    if nd is None:
        return ["No hay NDVI calculados todavía."]
    st = (nd.extra or {}).get("stats", {})
    lines = [f"Último NDVI: {nd.title}, NDVI medio {st.get('ndvi_mean')}, {st.get('valid_pct')} % del área válida."]
    ch = _latest(db, "raster_cambio")
    if ch is not None:
        cs = (ch.extra or {}).get("stats", {})
        lines.append(f"Última comparación: {ch.title}: disminución {cs.get('ndvi_decrease_km2')} km², aumento "
                     f"{cs.get('ndvi_increase_km2')} km². Un cambio de NDVI no confirma deforestación; está sin validar.")
    return lines


def _training_lines(db: Session) -> list[str]:
    rows = db.execute(select(AIModel.status, func.count()).group_by(AIModel.status)).all()
    if not rows:
        return ["No hay modelos registrados."]
    by = dict(rows)
    return [f"Modelos: {', '.join(f'{k} {v}' for k, v in by.items())}. "
            f"Validados: {by.get('validado', 0)}; los no validados son experimentales."]


def build_reply(db: Session, text: str, reg: ModuleRegistry,
                last_module: str | None = None) -> tuple[str, Interpretation]:
    it = interpret(text, reg)
    words = set(re.findall(r"[a-z0-9]+", normalize(text)))
    if it.intent == "desconocida" and last_module and words & _FOLLOW_UP and reg.get(last_module):
        # Memoria de sesión: continúa con el módulo de la respuesta anterior.
        it = Interpretation("seguimiento", last_module, sorted(words & _FOLLOW_UP))
    if it.intent == "estado_modulos":
        parts = [f"- {m.codename or m.name}: {m.status.value}" for m in reg.all()]
        return "Estado actual de los módulos (derivado de sus capacidades implementadas):\n" + "\n".join(parts), it
    if it.intent == "desconocida":
        return ("No reconocí la solicitud. Entiendo palabras clave en español sobre alertas, datos, módulos, "
                "terreno y escenarios 3D, NDVI, modelos y predicciones (por ejemplo «estado de los módulos», "
                "«cuántas alertas hay», «explícame la simulación», «qué predicciones hay»). "
                "Aún no uso un modelo de lenguaje."), it

    module = reg.get(it.module_key or "")
    assert module is not None
    lines = [f"Tu consulta corresponde a «{module.codename or module.name}» (estado: {module.status.value})."]
    if it.module_key == "alerts":
        total = _count(db, select(func.count()).select_from(Alert))
        unvalidated = _count(db, select(func.count()).where(Alert.validation_status == "no_validada"))
        high = _count(db, select(func.count()).where(Alert.level == "alto"))
        lines.append(f"Hay {total} alerta(s) experimental(es) registradas; {high} de nivel alto y "
                     f"{unvalidated} sin validar. Ninguna es una emergencia oficial.")
    elif it.module_key == "neurodata":
        total = _count(db, select(func.count()).select_from(DataRecord))
        scen = _count(db, select(func.count()).where(DataRecord.data_type.in_(SCENARIO_TYPES)))
        sim = _count(db, select(func.count()).where(DataRecord.is_simulated.is_(True),
                                                    DataRecord.data_type.not_in(SCENARIO_TYPES)))
        lines.append(f"NEURODATA contiene {total} registro(s): {total - sim - scen} con datos reales, {sim} de prueba "
                     f"(simulados) y {scen} escenario(s) hipotético(s) calculados por el sistema (no son observaciones).")
    elif it.module_key == "disasters":
        lines += _disaster_lines(db)
    elif it.module_key in ("neuro3d", "terrain"):
        lines += _scenario_lines(db)
    elif it.module_key == "neuroprediction":
        lines += _prediction_lines(db)
    elif it.module_key == "environmental":
        lines += _environment_lines(db)
    elif it.module_key == "neurotraining":
        lines += _training_lines(db)
    implemented = [c.description for c in module.capabilities if c.implemented]
    pending = [c.description for c in module.capabilities if not c.implemented]
    if implemented:
        lines.append("Disponible ahora: " + "; ".join(implemented) + ".")
    if pending:
        lines.append("Aún no implementado: " + "; ".join(pending) + ".")
    for lim in module.limitations[:3]:
        lines.append(f"Limitación: {lim}")
    return "\n".join(lines), it
