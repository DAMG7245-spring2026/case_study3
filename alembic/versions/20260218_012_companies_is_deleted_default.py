"""Add DEFAULT FALSE to companies.is_deleted

Revision ID: 012_companies_is_deleted_default
Revises: 011_assessments_add_org_air, 009_glassdoor_company_id
Create Date: 2026-02-18 00:00:00.000000

Note: Snowflake does not support ALTER COLUMN SET DEFAULT on existing columns.
Workaround: add new column with default, copy data, drop old, rename.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '012_companies_is_deleted_default'
down_revision: Union[str, tuple] = ('011_assessments_add_org_air', '009_glassdoor_company_id')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add replacement column with the DEFAULT
    op.add_column(
        'companies',
        sa.Column('is_deleted_new', sa.Boolean(), nullable=False, server_default=sa.text('FALSE'))
    )
    # 2. Copy existing data
    op.execute('UPDATE companies SET is_deleted_new = is_deleted')
    # 3. Drop old column
    op.drop_column('companies', 'is_deleted')
    # 4. Rename new column into place
    op.execute('ALTER TABLE companies RENAME COLUMN is_deleted_new TO is_deleted')


def downgrade() -> None:
    # Reverse: strip the default by recreating without server_default
    op.add_column(
        'companies',
        sa.Column('is_deleted_old', sa.Boolean(), nullable=False, server_default=sa.text('FALSE'))
    )
    op.execute('UPDATE companies SET is_deleted_old = is_deleted')
    op.drop_column('companies', 'is_deleted')
    op.execute('ALTER TABLE companies RENAME COLUMN is_deleted_old TO is_deleted')
