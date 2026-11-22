"""fase 3 entrenamiento de modelos

Revision ID: efe6f2f7b71a
Revises: 79e40e3a19e0
Create Date: 2026-11-22 14:16:28.968767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efe6f2f7b71a'
down_revision: Union[str, Sequence[str], None] = '79e40e3a19e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_VALIDATED_BY = 'fk_ai_models_validated_by_users'
FK_DATASET = 'fk_ai_models_dataset_record_id_data_records'


def upgrade() -> None:
    """Columnas para entrenamiento real. Los valores por defecto cubren los modelos ya registrados."""
    with op.batch_alter_table('ai_models', schema=None) as batch_op:
        batch_op.add_column(sa.Column('task', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('target', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('features', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('dataset_record_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('trained_with_simulated', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.add_column(sa.Column('artifact_sha256', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('validation_evidence', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('validated_by', sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(FK_VALIDATED_BY, 'users', ['validated_by'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(FK_DATASET, 'data_records', ['dataset_record_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('ai_models', schema=None) as batch_op:
        batch_op.drop_constraint(FK_DATASET, type_='foreignkey')
        batch_op.drop_constraint(FK_VALIDATED_BY, type_='foreignkey')
        for col in ('validated_by', 'validation_evidence', 'trained_at', 'artifact_sha256', 'trained_with_simulated',
                    'dataset_record_id', 'features', 'target', 'task'):
            batch_op.drop_column(col)
