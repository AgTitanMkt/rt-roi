"""create daily conversion breakdown table

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-03-31 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_daily_conversion_breakdown (
            metric_date DATE NOT NULL,
            squad TEXT NOT NULL,
            checkout TEXT NOT NULL,
            product TEXT NOT NULL,
            initiate_checkout NUMERIC(12,0) DEFAULT 0,
            purchase NUMERIC(12,0) DEFAULT 0,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT pk_tb_daily_conversion_breakdown PRIMARY KEY (metric_date, squad, checkout, product)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tb_daily_conversion_breakdown")

