"""motor de validación científica (SVE)

Revision ID: b3d8e2a41c07
Revises: f9ca7def1c5e
Create Date: 2026-11-24 18:00:00

Solo AÑADE tablas nuevas (no modifica ni borra datos existentes).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3d8e2a41c07"
down_revision: Union[str, Sequence[str], None] = "f9ca7def1c5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sv_experiments",
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("module_key", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("protocol_text", sa.Text(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("test_region", sa.JSON(), nullable=True),
        sa.Column("protocol_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="abierto", nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_sv_experiments_created_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sv_evaluations",
        sa.Column("experiment_id", sa.String(length=32), nullable=False),
        sa.Column("partition", sa.String(length=8), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=True),
        sa.Column("model_ref", sa.String(length=160), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("criteria_met", sa.Boolean(), nullable=False),
        sa.Column("criteria_detail", sa.JSON(), nullable=False),
        sa.Column("protocol_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["sv_experiments.id"],
                                name="fk_sv_evaluations_experiment_id_sv_experiments", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name="fk_sv_evaluations_run_id_runs", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_sv_evaluations_created_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sv_approvals",
        sa.Column("experiment_id", sa.String(length=32), nullable=False),
        sa.Column("evaluation_id", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.String(length=32), nullable=True),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["sv_experiments.id"],
                                name="fk_sv_approvals_experiment_id_sv_experiments", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["sv_evaluations.id"],
                                name="fk_sv_approvals_evaluation_id_sv_evaluations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], name="fk_sv_approvals_reviewer_id_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", "reviewer_id", name="uq_sv_approvals_evaluation_reviewer"),
    )
    with op.batch_alter_table("sv_evaluations", schema=None) as batch_op:
        batch_op.create_index("ix_sv_evaluations_experiment_id", ["experiment_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sv_evaluations", schema=None) as batch_op:
        batch_op.drop_index("ix_sv_evaluations_experiment_id")
    op.drop_table("sv_approvals")
    op.drop_table("sv_evaluations")
    op.drop_table("sv_experiments")
