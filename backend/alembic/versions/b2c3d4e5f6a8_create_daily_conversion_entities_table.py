"""create daily conversion entities table

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-31 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_daily_conversion_entities (
            metric_date DATE NOT NULL,
            campaign_id TEXT NOT NULL,
            offer_id TEXT,
            squad TEXT NOT NULL DEFAULT 'unknown',
            checkout TEXT NOT NULL DEFAULT 'unknown',
            product TEXT NOT NULL DEFAULT 'unknown',
            initiate_checkout NUMERIC(12,0) DEFAULT 0,
            purchase NUMERIC(12,0) DEFAULT 0,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT pk_tb_daily_conversion_entities PRIMARY KEY (metric_date, campaign_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tb_daily_conversion_entities")

