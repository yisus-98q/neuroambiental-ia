"""Eventos, alertas, modelos de IA, ejecuciones, predicciones, informes y conversaciones."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.common import IdMixin, TimestampMixin, utcnow


class Event(IdMixin, TimestampMixin, Base):
    """Un fenómeno observado o reportado (huayco, deslizamiento, derrame...)."""

    __tablename__ = "events"
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str] = mapped_column(String(128), default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Alert(IdMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    module_key: Mapped[str] = mapped_column(String(32), default="alerts")
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # bajo, medio, alto
    # Siempre "experimental": el sistema NO emite emergencias oficiales.
    alert_kind: Mapped[str] = mapped_column(String(16), default="experimental", nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False)
    # no_validada, en_revision, validada, descartada
    validation_status: Mapped[str] = mapped_column(String(16), default="no_validada", nullable=False)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    followups: Mapped[list[AlertFollowup]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", order_by="AlertFollowup.created_at"
    )


class AlertFollowup(IdMixin, TimestampMixin, Base):
    __tablename__ = "alert_followups"
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    new_status: Mapped[str | None] = mapped_column(String(16))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    alert: Mapped[Alert] = relationship(back_populates="followups")


class AIModel(IdMixin, TimestampMixin, Base):
    """Registro de modelos de NEUROTRAINING. Su estado debe ser honesto."""

    __tablename__ = "ai_models"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module_key: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), default="")
    version: Mapped[str] = mapped_column(String(32), default="0.0.0")
    # planificado, en_entrenamiento, entrenado, validado, retirado
    status: Mapped[str] = mapped_column(String(16), default="planificado", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_description: Mapped[str] = mapped_column(Text, default="")
    artifact_path: Mapped[str | None] = mapped_column(String(512))


class Run(IdMixin, Base):
    """Ejecución de un proceso (entrenamiento, análisis, importación)."""

    __tablename__ = "runs"
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    module_key: Mapped[str] = mapped_column(String(32), nullable=False)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="pendiente")  # pendiente, en_proceso, ok, error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class Prediction(IdMixin, TimestampMixin, Base):
    __tablename__ = "predictions"
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    model_id: Mapped[str | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"))
    territory_id: Mapped[str | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_evidence: Mapped[str] = mapped_column(Text, default="")


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    module_key: Mapped[str] = mapped_column(String(32), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(8), default="es")
    title: Mapped[str] = mapped_column(String(256), default="")

    messages: Mapped[list[ConversationMessage]] = relationship(
        cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversation_messages"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # usuario, asistente
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
