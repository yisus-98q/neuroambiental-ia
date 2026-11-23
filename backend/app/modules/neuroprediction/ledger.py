"""Catálogo unificado de resultados (sección 8): separa observación, histórico, procesamiento,
estimación, simulación, predicción y alerta. SIN tablas nuevas: todo se deriva de las existentes.

REGLAS DE CLASIFICACIÓN (cada elemento cae en EXACTAMENTE un tipo; las condiciones son disjuntas):

DataRecord (data_records)
  * data_type en {raster_ndvi, raster_cambio, imagen_procesada}  -> resultado_procesamiento
  * data_type == raster_escenario                                  -> simulacion
  * is_simulated=True (cualquier otro tipo)                        -> simulacion (dato de prueba)
  * is_simulated=False (csv, geojson, imagen, documento,
    medicion_manual, raster_dem, ...)                              -> observacion_real
Event (events)
  * is_simulated=True                                              -> simulacion
  * is_simulated=False y occurred_at en el pasado                  -> dato_historico
  * is_simulated=False sin fecha o con fecha futura                -> observacion_real (reporte sin fecha firme)
Run (runs)
  * run_type empieza por "escenario"                               -> simulacion
Prediction (predictions)
  * is_validated, modelo en estado "validado", modelo no entrenado con datos simulados y
    datos de entrada no simulados                                  -> prediccion
  * cualquier otra                                                 -> estimacion_modelo
Alert (alerts)
  * validation_status == "validada" y no simulada                  -> alerta_verificada
  * resto (no_validada, en_revision, descartada, o simulada)       -> alerta_experimental
    (subtipo NO verificado; nunca se cuenta como verificada)

Un elemento con is_simulated=True lleva simulated=True y JAMÁS es observacion_real, dato_historico,
prediccion ni alerta_verificada. Solo se leen metadatos: nunca se abren archivos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import AIModel, Alert, DataRecord, Event, Prediction, Run

MAX_LIMIT = 200
PRED_CAP = 2000  # las predicciones se clasifican en Python (el estado depende de JSON y de otra tabla)
PROCESSING = ("raster_ndvi", "raster_cambio", "imagen_procesada")
SCENARIO_TYPES = ("raster_escenario",)
NEVER_SIMULATED = ("observacion_real", "dato_historico", "prediccion", "alerta_verificada")

KINDS: dict[str, dict[str, Any]] = {
    "observacion_real": {
        "etiqueta": "Observación real", "verificado": True,
        "definicion": "Dato cargado o registrado manualmente, declarado como real y no derivado de un modelo.",
        "regla": "DataRecord no simulado que no sea producto de procesamiento ni escenario (csv, geojson, imagen, "
                 "documento, medicion_manual, raster_dem); evento real sin fecha pasada.",
        "incertidumbre": "Depende del instrumento y de la calidad declarada; la carga no certifica la medición.",
        "limitaciones": ["La condición «real» es una declaración de quien cargó el dato; el sistema no la verifica."],
        "verificacion": "Contrastar con la fuente original y revisar la calidad y la cadena de custodia.",
    },
    "dato_historico": {
        "etiqueta": "Dato histórico", "verificado": True,
        "definicion": "Evento real ocurrido en el pasado, registrado en el sistema.",
        "regla": "Evento con is_simulated=False y occurred_at anterior a hoy.",
        "incertidumbre": "Fecha y ubicación según la fuente que reportó el evento.",
        "limitaciones": ["El registro puede ser incompleto o provenir de un reporte no oficial."],
        "verificacion": "Contrastar con registros oficiales (INDECI, municipalidad, prensa verificable).",
    },
    "resultado_procesamiento": {
        "etiqueta": "Resultado de procesamiento", "verificado": False,
        "definicion": "Producto determinista calculado a partir de datos (NDVI, cambio, imagen procesada); no es un modelo.",
        "regla": "DataRecord con data_type raster_ndvi, raster_cambio o imagen_procesada.",
        "incertidumbre": "Hereda la de los datos de entrada y de las correcciones aplicadas (atmosféricas, nubes).",
        "limitaciones": ["Es un cálculo, no una interpretación: requiere criterio experto para atribuir causas."],
        "verificacion": "Comprobar con trabajo de campo o con una fuente independiente de la misma fecha.",
    },
    "estimacion_modelo": {
        "etiqueta": "Estimación de modelo", "verificado": False,
        "definicion": "Salida de un modelo entrenado que NO ha sido validado: experimental.",
        "regla": "Prediction cuyo modelo no cumple todas las condiciones de «prediccion».",
        "incertidumbre": "Alta y no cuantificada: sin validación con datos independientes.",
        "limitaciones": ["Sin validación externa.", "Probabilidades del modelo NO calibradas.",
                         "Sin horizonte temporal definido."],
        "verificacion": "Validar con datos independientes antes de usarla para decidir.",
    },
    "simulacion": {
        "etiqueta": "Simulación", "verificado": False,
        "definicion": "Escenario hipotético o dato de prueba: no describe un hecho real ni un pronóstico.",
        "regla": "Run de escenario, raster_escenario, o cualquier DataRecord/evento marcado is_simulated=True.",
        "incertidumbre": "Depende de la resolución del terreno y de supuestos simplificados; no cuantificada.",
        "limitaciones": ["Resultado de un método simplificado; no sustituye un estudio hidrológico o geotécnico."],
        "verificacion": "Contrastar con un estudio técnico y con observaciones de campo.",
    },
    "prediccion": {
        "etiqueta": "Predicción validada", "verificado": True,
        "definicion": "Salida de un modelo validado por un administrador con evidencia independiente.",
        "regla": "Prediction validada, modelo en estado validado, sin datos simulados de entrenamiento ni de entrada.",
        "incertidumbre": "Moderada y acotada por las métricas de validación; sigue habiendo error.",
        "limitaciones": ["Válida solo dentro del dominio de los datos de validación.",
                         "El sistema no define horizonte temporal ni calibra probabilidades."],
        "verificacion": "Monitorear contra observaciones nuevas y revalidar al reentrenar.",
    },
    "alerta_verificada": {
        "etiqueta": "Alerta verificada", "verificado": True,
        "definicion": "Alerta experimental cuya validación humana quedó registrada como «validada».",
        "regla": "Alert con validation_status=validada y is_simulated=False. No es una emergencia oficial.",
        "incertidumbre": "Texto de incertidumbre de la propia alerta.",
        "limitaciones": ["No es una emergencia oficial: para eso consulte INDECI / COEN."],
        "verificacion": "Coordinar con autoridades competentes antes de actuar.",
    },
    "alerta_experimental": {
        "etiqueta": "Alerta experimental (no verificada)", "verificado": False,
        "definicion": "Alerta sin validar, en revisión, descartada o simulada. Subtipo NO verificado.",
        "regla": "Alert que no cumple las condiciones de alerta_verificada.",
        "incertidumbre": "Texto de incertidumbre de la propia alerta; sin validación humana completa.",
        "limitaciones": ["No es una emergencia oficial.", "Sin validación humana concluida."],
        "verificacion": "Validar con evidencia de campo o de fuentes oficiales antes de difundirla.",
    },
}


def _now(db: Session) -> datetime:
    n = datetime.now(timezone.utc)
    return n.replace(tzinfo=None) if db.get_bind().dialect.name == "sqlite" else n


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _loc(lat: float | None, lon: float | None, bbox: list | None = None) -> dict | None:
    if lat is not None and lon is not None:
        return {"lat": lat, "lon": lon}
    return {"bbox": bbox} if bbox else None


def _item(tipo: str, id_: str, titulo: str, simulated: bool, **kw: Any) -> dict:
    k = KINDS[tipo]
    assert not (simulated and tipo in NEVER_SIMULATED), f"un elemento simulado no puede ser {tipo}"
    return {
        "id": id_, "tipo": tipo, "titulo": titulo, "ubicacion": kw.get("ubicacion"),
        "fecha_analisis": _iso(kw.get("fecha_analisis")), "fecha_observacion": _iso(kw.get("fecha_observacion")),
        "datos_utilizados": kw.get("datos", []), "modelo": kw.get("modelo"), "version": kw.get("version"),
        "horizonte_temporal": None,  # el sistema no define horizontes: nunca se inventa
        "resultado": kw.get("resultado", ""), "probabilidad": kw.get("probabilidad"),
        "probabilidad_nota": kw.get("probabilidad_nota", "No aplica."),
        "incertidumbre": kw.get("incertidumbre") or k["incertidumbre"],
        "evidencias": kw.get("evidencias", []),
        "limitaciones": list(k["limitaciones"]),
        "recomendaciones_de_verificacion": k["verificacion"],
        "simulated": simulated, "verificado": k["verificado"] and not simulated,
    }


# --- mapeadores ---------------------------------------------------------------------------------
def _from_record(tipo: str, r: DataRecord) -> dict:
    ev = [f"Estado de validación del dato: {r.validation_status}", f"Calidad: {r.quality}"]
    if r.sha256:
        ev.append(f"SHA-256: {r.sha256[:16]}…")
    if r.provenance:
        ev.append(f"Procedencia: {r.provenance[:200]}")
    src = r.source.name if r.source else ""
    val = f" = {r.value} {r.unit}".rstrip() if r.value is not None else ""
    return _item(tipo, r.id, r.title or f"{r.data_type} {r.id[:8]}", r.is_simulated,
                 ubicacion=_loc(r.latitude, r.longitude, r.bbox), fecha_analisis=r.received_at,
                 fecha_observacion=r.observed_at, datos=[{"data_record": r.id, "fuente": src}],
                 resultado=f"Registro «{r.data_type}»{val}", evidencias=ev)


def _from_event(tipo: str, e: Event) -> dict:
    return _item(tipo, e.id, e.title, e.is_simulated, ubicacion=_loc(e.latitude, e.longitude),
                 fecha_analisis=e.created_at, fecha_observacion=e.occurred_at,
                 datos=[{"evento": e.id, "fuente": e.source_name}], resultado=f"Evento «{e.event_type}»",
                 evidencias=[e.description[:300]] if e.description else [])


def _from_run(db: Session, r: Run) -> dict:
    p = r.parameters or {}
    rec = db.get(DataRecord, p["record_id"]) if isinstance(p.get("record_id"), str) else None
    simulated = bool(rec.is_simulated) if rec else False
    return _item("simulacion", r.id, f"Escenario «{r.run_type}»", simulated,
                 ubicacion=_loc(p.get("lat"), p.get("lon")), fecha_analisis=r.finished_at or r.started_at,
                 datos=[{"data_record": p["record_id"]}] if rec else [], modelo=p.get("metodo"),
                 resultado=f"Ejecución {r.run_type}, estado {r.status}",
                 evidencias=[f"Parámetros: {', '.join(sorted(p))}"] if p else [])


def _from_alert(a: Alert) -> dict:
    ok = a.validation_status == "validada" and not a.is_simulated
    return _item("alerta_verificada" if ok else "alerta_experimental", a.id, a.title, a.is_simulated,
                 ubicacion=_loc(a.latitude, a.longitude), fecha_analisis=a.created_at, fecha_observacion=a.observed_at,
                 datos=[{"alerta": a.id, "fuente": a.source_name}],
                 resultado=f"Nivel {a.level}; estado de validación: {a.validation_status}",
                 incertidumbre=a.uncertainty, evidencias=[a.evidence[:300]] if a.evidence else [])


def _classify_prediction(p: Prediction, m: AIModel | None) -> str:
    v = p.value or {}
    if (p.is_validated and m is not None and m.status == "validado" and not m.trained_with_simulated
            and not v.get("input_simulated", True)):
        return "prediccion"
    return "estimacion_modelo"


def _from_prediction(tipo: str, p: Prediction, m: AIModel | None) -> dict:
    v = p.value or {}
    prob, nota = None, "No calibrada / no validada."
    if tipo == "prediccion":
        probs = [r["model_probability"] for r in v.get("sample", []) if isinstance(r, dict)
                 and isinstance(r.get("model_probability"), (int, float))]
        if probs:
            prob = round(sum(probs) / len(probs), 4)
            nota = "Media de la probabilidad del modelo en la muestra; el modelo está validado pero NO calibrado."
        else:
            nota = "El modelo está validado pero esta predicción no contiene probabilidades."
    simulated = bool(v.get("input_simulated", False) or (m is not None and m.trained_with_simulated))
    return _item(tipo, p.id, f"Estimación de «{p.target}»" + (f" · {m.name}" if m else ""), simulated,
                 fecha_analisis=p.created_at, datos=[{"data_record": v["dataset"]}] if v.get("dataset") else [],
                 modelo=(m.algorithm or m.name) if m else None, version=m.version if m else None,
                 resultado=str(v.get("summary", {}))[:300], probabilidad=prob, probabilidad_nota=nota,
                 incertidumbre=p.uncertainty,
                 evidencias=[p.validation_evidence[:300]] if p.validation_evidence else
                 [f"Filas evaluadas: {v.get('n', 'n/d')}"])


# --- consultas por fuente -----------------------------------------------------------------------
def _record_where(tipo: str) -> Any:
    sim = DataRecord.is_simulated.is_(True)
    proc = DataRecord.data_type.in_(PROCESSING)
    scen = DataRecord.data_type.in_(SCENARIO_TYPES)
    return {"resultado_procesamiento": proc, "simulacion": or_(scen, and_(sim, ~proc)),
            "observacion_real": and_(~sim, ~proc, ~scen)}[tipo]


def _event_where(tipo: str, now: datetime) -> Any:
    real, dated = Event.is_simulated.is_(False), and_(Event.occurred_at.is_not(None), Event.occurred_at < now)
    return {"simulacion": Event.is_simulated.is_(True), "dato_historico": and_(real, dated),
            "observacion_real": and_(real, ~dated)}[tipo]


def _alert_where(tipo: str) -> Any:
    ok = and_(Alert.validation_status == "validada", Alert.is_simulated.is_(False))
    return ok if tipo == "alerta_verificada" else ~ok


def _count(db: Session, model: Any, where: Any) -> int:
    return db.scalar(select(func.count()).select_from(model).where(where)) or 0


def _predictions(db: Session, tipo: str) -> list[dict]:
    rows = db.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(PRED_CAP)).all()
    ids = {p.model_id for p in rows if p.model_id}
    models = {m.id: m for m in db.scalars(select(AIModel).where(AIModel.id.in_(ids)))} if ids else {}
    out = []
    for p in rows:
        m = models.get(p.model_id)
        if _classify_prediction(p, m) == tipo:
            out.append(_from_prediction(tipo, p, m))
    return out


def _sources(tipo: str, db: Session) -> list[tuple[Any, Any, Callable[[Any], dict], Any]]:
    """Fuentes (modelo, filtro, mapeador, columna de orden) que alimentan un tipo."""
    now, out = _now(db), []
    if tipo in ("observacion_real", "resultado_procesamiento", "simulacion"):
        out.append((DataRecord, _record_where(tipo), lambda r, t=tipo: _from_record(t, r), DataRecord.received_at))
    if tipo in ("observacion_real", "dato_historico", "simulacion"):
        out.append((Event, _event_where(tipo, now), lambda e, t=tipo: _from_event(t, e), Event.created_at))
    if tipo == "simulacion":
        out.append((Run, Run.run_type.like("escenario%"), lambda r: _from_run(db, r), Run.started_at))
    if tipo in ("alerta_verificada", "alerta_experimental"):
        out.append((Alert, _alert_where(tipo), _from_alert, Alert.created_at))
    return out


def count_kind(db: Session, tipo: str) -> int:
    if tipo in ("estimacion_modelo", "prediccion"):
        return len(_predictions(db, tipo))
    return sum(_count(db, m, w) for m, w, _, _ in _sources(tipo, db))


def list_kind(db: Session, tipo: str, take: int) -> list[dict]:
    """Los `take` elementos más recientes del tipo (take = offset + limit)."""
    if tipo in ("estimacion_modelo", "prediccion"):
        return _predictions(db, tipo)[:take]
    items: list[dict] = []
    for model, where, mapper, order in _sources(tipo, db):
        q = select(model).where(where).order_by(order.desc()).limit(take)
        if model is DataRecord:
            q = q.options(joinedload(DataRecord.source))
        items += [mapper(r) for r in db.scalars(q).unique()]
    return items


def catalog(db: Session, tipo: str | None, limit: int, offset: int) -> dict:
    limit, offset = min(max(limit, 1), MAX_LIMIT), max(offset, 0)
    totales = {k: count_kind(db, k) for k in KINDS}
    items: list[dict] = []
    for k in [tipo] if tipo else list(KINDS):
        items += list_kind(db, k, offset + limit)
    items.sort(key=lambda i: i["fecha_analisis"] or "", reverse=True)
    return {"total": totales[tipo] if tipo else sum(totales.values()), "totales_por_tipo": totales,
            "limit": limit, "offset": offset, "items": items[offset:offset + limit]}


def detail(db: Session, tipo: str, id_: str) -> dict | None:
    if tipo in ("estimacion_modelo", "prediccion"):
        p = db.get(Prediction, id_)
        m = db.get(AIModel, p.model_id) if p and p.model_id else None
        return _from_prediction(tipo, p, m) if p and _classify_prediction(p, m) == tipo else None
    for model, where, mapper, _ in _sources(tipo, db):
        row = db.scalars(select(model).where(model.id == id_, where)).first()
        if row is not None:
            return mapper(row)
    return None
