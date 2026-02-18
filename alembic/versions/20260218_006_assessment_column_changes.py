"""Modify assessments: drop primary/secondary_assessor, add h_r_score and synergy

Revision ID: 006_assessment_cols
Revises: 005_signal_raw, 004_created_at_nullable
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_assessment_cols'
down_revision: Union[str, tuple] = ('005_signal_raw', '004_created_at_nullable')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('assessments', 'primary_assessor')
    op.drop_column('assessments', 'secondary_assessor')
    op.add_column('assessments', sa.Column('h_r_score', sa.Float(), nullable=True))
    op.add_column('assessments', sa.Column('synergy', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('assessments', 'h_r_score')
    op.drop_column('assessments', 'synergy')
    op.add_column('assessments', sa.Column('primary_assessor', sa.String(255), nullable=True))
    op.add_column('assessments', sa.Column('secondary_assessor', sa.String(255), nullable=True))
