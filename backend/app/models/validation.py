"""Scientific Validation Engine: experimentos con criterios congelados, evaluaciones y aprobaciones."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.common import IdMixin, TimestampMixin

PARTITIONS = ("cv", "test")
DECISIONS = ("aprobar", "rechazar")


class Experiment(IdMixin, TimestampMixin, Base):
    """Pregunta + protocolo + criterios + región de prueba. Inmutable: cambiar algo = experimento nuevo."""

    __tablename__ = "sv_experiments"
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    module_key: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    protocol_text: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    test_region: Mapped[list | None] = mapped_column(JSON)          # bbox [minLon, minLat, maxLon, maxLat]
    protocol_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="abierto", server_default="abierto")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_sv_experiments_created_by_users", ondelete="SET NULL"))


class Evaluation(IdMixin, TimestampMixin, Base):
    __tablename__ = "sv_evaluations"
    __table_args__ = (Index("ix_sv_evaluations_experiment_id", "experiment_id"),)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("sv_experiments.id", name="fk_sv_evaluations_experiment_id_sv_experiments", ondelete="CASCADE"),
        nullable=False)
    partition: Mapped[str] = mapped_column(String(8), nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id", name="fk_sv_evaluations_run_id_runs", ondelete="SET NULL"))
    model_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    criteria_met: Mapped[bool] = mapped_column(Boolean, nullable=False)
    criteria_detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    protocol_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_sv_evaluations_created_by_users", ondelete="SET NULL"))


class Approval(IdMixin, TimestampMixin, Base):
    __tablename__ = "sv_approvals"
    __table_args__ = (UniqueConstraint("evaluation_id", "reviewer_id", name="uq_sv_approvals_evaluation_reviewer"),)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("sv_experiments.id", name="fk_sv_approvals_experiment_id_sv_experiments", ondelete="CASCADE"),
        nullable=False)
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("sv_evaluations.id", name="fk_sv_approvals_evaluation_id_sv_evaluations", ondelete="CASCADE"),
        nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", name="fk_sv_approvals_reviewer_id_users", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
