"""Add signal_raw_collections table - v5.0

Revision ID: 005_signal_raw
Revises: 004_companies_urls
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from snowflake.sqlalchemy import VARIANT

revision: str = '005_signal_raw'
down_revision: Union[str, None] = '004_companies_urls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'signal_raw_collections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
        sa.Column('payload', VARIANT, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('company_id', 'category', name='uq_signal_raw_company_category'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
    )


def downgrade() -> None:
    op.drop_table('signal_raw_collections')
