"""Change h_r_score and synergy from FLOAT to NUMBER(5,2)

Revision ID: 007_assessment_score_types
Revises: 006_assessment_cols
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_assessment_score_types'
down_revision: Union[str, None] = '006_assessment_cols'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Snowflake cannot cast FLOAT → NUMBER directly.
    # Strategy: add temp column, copy data, drop old, rename.
    for col in ('h_r_score', 'synergy'):
        op.add_column('assessments', sa.Column(f'{col}_new', sa.Numeric(5, 2), nullable=True))
        op.execute(f'UPDATE assessments SET {col}_new = {col}')
        op.drop_column('assessments', col)
        op.execute(f'ALTER TABLE assessments RENAME COLUMN {col}_new TO {col}')


def downgrade() -> None:
    for col in ('h_r_score', 'synergy'):
        op.add_column('assessments', sa.Column(f'{col}_old', sa.Float(), nullable=True))
        op.execute(f'UPDATE assessments SET {col}_old = {col}')
        op.drop_column('assessments', col)
        op.execute(f'ALTER TABLE assessments RENAME COLUMN {col}_old TO {col}')
