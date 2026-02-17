"""Add URL columns to companies - v4.0

Revision ID: 004_companies_urls
Revises: 003_signal_summaries
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_companies_urls'
down_revision: Union[str, None] = '003_signal_summaries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('domain', sa.String(500), nullable=True))
    op.add_column('companies', sa.Column('careers_url', sa.String(500), nullable=True))
    op.add_column('companies', sa.Column('news_url', sa.String(500), nullable=True))
    op.add_column('companies', sa.Column('leadership_url', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'leadership_url')
    op.drop_column('companies', 'news_url')
    op.drop_column('companies', 'careers_url')
    op.drop_column('companies', 'domain')
