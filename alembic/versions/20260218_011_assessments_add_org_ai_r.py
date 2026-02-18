"""Add org_ai_r column to assessments

Revision ID: 011_assessments_add_org_air
Revises: 010_assessments_drop_type_status
Create Date: 2026-02-18 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '011_assessments_add_org_air'
down_revision: Union[str, None] = '010_assessments_drop_type_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'assessments',
        sa.Column('org_ai_r', sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('assessments', 'org_ai_r')
