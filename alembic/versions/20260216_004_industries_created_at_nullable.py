"""Make industries.created_at nullable

Revision ID: 004_created_at_nullable
Revises: 003_signal_summaries
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_created_at_nullable'
down_revision: Union[str, None] = '003_signal_summaries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow NULL values in industries.created_at."""
    op.alter_column('industries', 'created_at',
                     existing_type=sa.DateTime(),
                     nullable=True)


def downgrade() -> None:
    """Revert industries.created_at to NOT NULL."""
    op.alter_column('industries', 'created_at',
                     existing_type=sa.DateTime(),
                     nullable=False)
