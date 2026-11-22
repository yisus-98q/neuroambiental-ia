from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import audit
from app.core.security import get_current_user, require_role
from app.database.session import get_db
from app.models import Alert, AlertFollowup, Event, Report, User
from app.schemas import AlertIn, AlertOut, EventIn, EventOut, FollowupIn

router = APIRouter(prefix="/api/alerts", tags=["Alertas y Prevención"])

DISCLAIMER = ("ALERTA EXPERIMENTAL generada por NEUROAMBIENTAL IA. No es una emergencia oficial. "
              "Para emergencias oficiales en Perú consulte a INDECI / COEN y a las autoridades locales.")


def _get(db: Session, alert_id: str) -> Alert:
    alert = db.scalar(select(Alert).options(selectinload(Alert.followups)).where(Alert.id == alert_id))
    if alert is None:
        raise HTTPException(404, "Alerta no encontrada.")
    return alert


@router.get("", response_model=list[AlertOut])
def list_alerts(level: str | None = None, validation_status: str | None = None, limit: int = 100,
                _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Alert]:
    q = select(Alert).options(selectinload(Alert.followups)).order_by(Alert.created_at.desc())
    if level:
        q = q.where(Alert.level == level)
    if validation_status:
        q = q.where(Alert.validation_status == validation_status)
    return list(db.scalars(q.limit(min(max(limit, 1), 500))))


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(body: AlertIn, user: User = Depends(require_role("analista")),
                 db: Session = Depends(get_db)) -> Alert:
    alert = Alert(**body.model_dump(), alert_kind="experimental", created_by=user.id)
    db.add(alert)
    db.flush()
    audit(db, "crear_alerta", user_id=user.id, target_type="alert", target_id=alert.id,
          details={"nivel": body.level, "simulada": body.is_simulated}, commit=False)
    db.commit()
    return _get(db, alert.id)


@router.get("/geojson")
def alerts_geojson(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Alert).where(Alert.latitude.is_not(None)).order_by(Alert.created_at.desc()).limit(1000))
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [a.longitude, a.latitude]},
         "properties": {"alert_id": a.id, "title": a.title, "level": a.level, "validation_status": a.validation_status,
                        "alert_kind": a.alert_kind, "is_simulated": a.is_simulated, "source": a.source_name}}
        for a in rows]}


@router.get("/events", response_model=list[EventOut])
def list_events(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Event]:
    return list(db.scalars(select(Event).order_by(Event.created_at.desc()).limit(200)))


@router.post("/events", response_model=EventOut, status_code=201)
def create_event(body: EventIn, user: User = Depends(require_role("analista")),
                 db: Session = Depends(get_db)) -> Event:
    event = Event(**body.model_dump(), created_by=user.id)
    db.add(event)
    db.flush()
    audit(db, "crear_evento", user_id=user.id, target_type="event", target_id=event.id, commit=False)
    db.commit()
    return event


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Alert:
    return _get(db, alert_id)


@router.post("/{alert_id}/followups", response_model=AlertOut, status_code=201)
def add_followup(alert_id: str, body: FollowupIn, user: User = Depends(require_role("analista")),
                 db: Session = Depends(get_db)) -> Alert:
    alert = _get(db, alert_id)
    db.add(AlertFollowup(alert_id=alert.id, note=body.note, new_status=body.new_status, created_by=user.id))
    if body.new_status:
        alert.validation_status = body.new_status
    audit(db, "seguimiento_alerta", user_id=user.id, target_type="alert", target_id=alert.id,
          details={"nuevo_estado": body.new_status}, commit=False)
    db.commit()
    db.expire(alert)
    return _get(db, alert_id)


def render_report(a: Alert) -> str:
    loc = f"{a.latitude:.5f}, {a.longitude:.5f}" if a.latitude is not None else "sin ubicación"
    lines = [
        f"# Informe de alerta: {a.title}", "", f"> {DISCLAIMER}", "",
        f"- **ID:** {a.id}", f"- **Tipo:** {a.alert_kind}", f"- **Nivel:** {a.level}",
        f"- **Estado de validación:** {a.validation_status}",
        f"- **Datos simulados:** {'SÍ' if a.is_simulated else 'no'}",
        f"- **Ubicación (lat, lon):** {loc}", f"- **Fuente:** {a.source_name}",
        f"- **Fecha de observación:** {a.observed_at or 'no indicada'}", f"- **Registrada:** {a.created_at}",
        "", "## Descripción", a.description or "(sin descripción)", "", "## Evidencia", a.evidence or "(sin evidencia)",
        "", "## Incertidumbre", a.uncertainty, "", "## Seguimiento",
    ]
    if not a.followups:
        lines.append("(sin seguimientos)")
    for f in a.followups:
        status = f" → estado: {f.new_status}" if f.new_status else ""
        lines.append(f"- {f.created_at}: {f.note}{status}")
    return "\n".join(lines) + "\n"


@router.post("/{alert_id}/report")
def create_report(alert_id: str, user: User = Depends(require_role("analista")),
                  db: Session = Depends(get_db)) -> dict:
    alert = _get(db, alert_id)
    content = render_report(alert)
    report = Report(title=f"Informe de alerta: {alert.title}", module_key="alerts", content_md=content,
                    created_by=user.id)
    db.add(report)
    db.flush()
    audit(db, "informe_alerta", user_id=user.id, target_type="report", target_id=report.id, commit=False)
    db.commit()
    return {"report_id": report.id, "title": report.title, "content_md": content}
