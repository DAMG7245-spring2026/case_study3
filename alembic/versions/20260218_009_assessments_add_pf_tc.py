"""Add position_factor and talent_concentration columns to assessments

Revision ID: 009_assessments_add_pf_tc
Revises: 008_dimension_score_restructure
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '009_assessments_add_pf_tc'
down_revision: Union[str, None] = '008_dimension_score_restructure'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Position Factor: bounded [-1, 1], 4 decimal places
    op.add_column(
        'assessments',
        sa.Column('position_factor', sa.Numeric(5, 4), nullable=True),
    )
    # Talent Concentration: bounded [0, 1], 4 decimal places
    op.add_column(
        'assessments',
        sa.Column('talent_concentration', sa.Numeric(5, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('assessments', 'talent_concentration')
    op.drop_column('assessments', 'position_factor')
