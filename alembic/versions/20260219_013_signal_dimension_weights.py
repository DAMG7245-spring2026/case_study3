"""Add signal_dimension_weights table and weights_hash to dimension_scores

Revision ID: 013_signal_dimension_weights
Revises: 012_companies_is_deleted_default
Create Date: 2026-02-19 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '013_signal_dimension_weights'
down_revision: Union[str, None] = '012_companies_is_deleted_default'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add weights_hash to dimension_scores
    op.add_column(
        'dimension_scores',
        sa.Column('weights_hash', sa.String(64), nullable=True),
    )

    # 2. Create signal_dimension_weights table
    op.create_table(
        'signal_dimension_weights',
        sa.Column('signal_source', sa.String(50), nullable=False),
        sa.Column('dimension', sa.String(30), nullable=False),
        sa.Column('weight', sa.Numeric(6, 4), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column('reliability', sa.Numeric(6, 4), nullable=False, server_default=sa.text('0.80')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP()')),
        sa.Column('updated_by', sa.String(100), nullable=True, server_default=sa.text("'system'")),
        sa.PrimaryKeyConstraint('signal_source', 'dimension'),
    )

    # 3. Seed default weights via MERGE (idempotent re-run)
    op.execute("""
        MERGE INTO signal_dimension_weights AS target
        USING (
            SELECT 'technology_hiring'  AS signal_source, 'technology_stack'    AS dimension, 0.7  AS weight, TRUE  AS is_primary, 0.9  AS reliability UNION ALL
            SELECT 'technology_hiring',                    'talent_skills',                   0.2,             FALSE,              0.9  UNION ALL
            SELECT 'technology_hiring',                    'use_case_portfolio',               0.1,             FALSE,              0.9  UNION ALL
            SELECT 'innovation_activity',                  'technology_stack',                0.8,             TRUE,               0.85 UNION ALL
            SELECT 'innovation_activity',                  'use_case_portfolio',               0.1,             FALSE,              0.85 UNION ALL
            SELECT 'innovation_activity',                  'culture_change',                  0.1,             FALSE,              0.85 UNION ALL
            SELECT 'digital_presence',                     'technology_stack',                0.6,             TRUE,               0.75 UNION ALL
            SELECT 'digital_presence',                     'data_infrastructure',             0.4,             FALSE,              0.75 UNION ALL
            SELECT 'leadership_signals',                   'leadership_vision',               0.7,             TRUE,               0.95 UNION ALL
            SELECT 'leadership_signals',                   'culture_change',                  0.1,             FALSE,              0.95 UNION ALL
            SELECT 'leadership_signals',                   'ai_governance',                   0.2,             FALSE,              0.95 UNION ALL
            SELECT 'sec_item_1',                           'use_case_portfolio',               0.5,             TRUE,               0.95 UNION ALL
            SELECT 'sec_item_1',                           'technology_stack',                0.2,             FALSE,              0.95 UNION ALL
            SELECT 'sec_item_1',                           'leadership_vision',               0.3,             FALSE,              0.95 UNION ALL
            SELECT 'sec_item_1a',                          'ai_governance',                   0.6,             TRUE,               0.9  UNION ALL
            SELECT 'sec_item_1a',                          'data_infrastructure',             0.4,             FALSE,              0.9  UNION ALL
            SELECT 'sec_item_7',                           'leadership_vision',               0.6,             TRUE,               0.9  UNION ALL
            SELECT 'sec_item_7',                           'use_case_portfolio',               0.2,             FALSE,              0.9  UNION ALL
            SELECT 'sec_item_7',                           'data_infrastructure',             0.2,             FALSE,              0.9  UNION ALL
            SELECT 'glassdoor_reviews',                    'culture_change',                  0.8,             TRUE,               0.6  UNION ALL
            SELECT 'glassdoor_reviews',                    'talent_skills',                   0.1,             FALSE,              0.6  UNION ALL
            SELECT 'glassdoor_reviews',                    'leadership_vision',               0.1,             FALSE,              0.6  UNION ALL
            SELECT 'board_composition',                    'ai_governance',                   0.7,             TRUE,               0.85 UNION ALL
            SELECT 'board_composition',                    'leadership_vision',               0.3,             FALSE,              0.85
        ) AS source
        ON target.signal_source = source.signal_source AND target.dimension = source.dimension
        WHEN NOT MATCHED THEN
            INSERT (signal_source, dimension, weight, is_primary, reliability)
            VALUES (source.signal_source, source.dimension, source.weight, source.is_primary, source.reliability)
        WHEN MATCHED THEN
            UPDATE SET
                weight      = source.weight,
                is_primary  = source.is_primary,
                reliability = source.reliability,
                updated_at  = CURRENT_TIMESTAMP(),
                updated_by  = 'seed'
    """)


def downgrade() -> None:
    op.drop_table('signal_dimension_weights')
    op.drop_column('dimension_scores', 'weights_hash')
