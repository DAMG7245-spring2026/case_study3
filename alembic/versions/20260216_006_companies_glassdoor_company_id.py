"""Add glassdoor_company_id to companies (after dimension_score restructure)

Revision ID: 009_glassdoor_company_id
Revises: 008_dimension_score_restructure
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '009_glassdoor_company_id'
down_revision: Union[str, None] = '008_dimension_score_restructure'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS so this is safe to re-run on Snowflake
    # instances where the column was already applied outside of Alembic.
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS glassdoor_company_id VARCHAR(20)")


def downgrade() -> None:
    op.drop_column('companies', 'glassdoor_company_id')
