"""Drop assessment_type and status columns from assessments

Revision ID: 010_assessments_drop_type_status
Revises: 009_assessments_add_pf_tc
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '010_assessments_drop_type_status'
down_revision: Union[str, None] = '009_assessments_add_pf_tc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('assessments', 'assessment_type')
    op.drop_column('assessments', 'status')


def downgrade() -> None:
    op.add_column('assessments', sa.Column('status', sa.String(50), nullable=True))
    op.add_column('assessments', sa.Column('assessment_type', sa.String(50), nullable=True))
