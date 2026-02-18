"""Restructure dimension_scores: assessment_id→company_id, weight→total_weight, add contributing_sources

Revision ID: 008_dimension_score_restructure
Revises: 007_assessment_score_types
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from snowflake.sqlalchemy import VARIANT

revision: str = '008_dimension_score_restructure'
down_revision: Union[str, None] = '007_assessment_score_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add company_id as nullable first (populated via join below)
    op.add_column('dimension_scores', sa.Column('company_id', sa.String(36), nullable=True))

    # 2. Backfill company_id from assessments
    op.execute(
        'UPDATE dimension_scores '
        'SET company_id = a.company_id '
        'FROM assessments a '
        'WHERE a.id = dimension_scores.assessment_id'
    )

    # 3. Drop old FK column
    op.drop_column('dimension_scores', 'assessment_id')

    # 4. Rename weight → total_weight (add+copy+drop pattern for Snowflake)
    op.add_column('dimension_scores', sa.Column('total_weight', sa.Float(), nullable=True))
    op.execute('UPDATE dimension_scores SET total_weight = weight')
    op.drop_column('dimension_scores', 'weight')

    # 5. Add contributing_sources VARIANT
    op.add_column('dimension_scores', sa.Column('contributing_sources', VARIANT, nullable=True))


def downgrade() -> None:
    # Remove contributing_sources
    op.drop_column('dimension_scores', 'contributing_sources')

    # Rename total_weight → weight
    op.add_column('dimension_scores', sa.Column('weight', sa.Float(), nullable=True))
    op.execute('UPDATE dimension_scores SET weight = total_weight')
    op.drop_column('dimension_scores', 'total_weight')

    # Restore assessment_id (best-effort: NULL since original mapping is lost)
    op.add_column('dimension_scores', sa.Column('assessment_id', sa.String(36), nullable=True))

    # Drop company_id
    op.drop_column('dimension_scores', 'company_id')
