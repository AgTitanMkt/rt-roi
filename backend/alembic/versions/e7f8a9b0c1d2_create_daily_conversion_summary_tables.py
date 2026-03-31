"""create daily conversion summary tables

Revision ID: e7f8a9b0c1d2
Revises: ef5cb58dc7db
Create Date: 2026-03-31 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "ef5cb58dc7db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_hourly_metrics') IS NOT NULL THEN
                ALTER TABLE tb_hourly_metrics
                ADD COLUMN IF NOT EXISTS checkout_type TEXT;

                ALTER TABLE tb_hourly_metrics
                ADD COLUMN IF NOT EXISTS product TEXT;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_daily_checkout_summary (
            metric_date DATE NOT NULL,
            checkout TEXT NOT NULL,
            squad TEXT NOT NULL DEFAULT 'ALL',
            initiate_checkout NUMERIC(12,0) DEFAULT 0,
            purchase NUMERIC(12,0) DEFAULT 0,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT pk_tb_daily_checkout_summary PRIMARY KEY (metric_date, checkout, squad)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_daily_product_summary (
            metric_date DATE NOT NULL,
            product TEXT NOT NULL,
            squad TEXT NOT NULL DEFAULT 'ALL',
            initiate_checkout NUMERIC(12,0) DEFAULT 0,
            purchase NUMERIC(12,0) DEFAULT 0,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT pk_tb_daily_product_summary PRIMARY KEY (metric_date, product, squad)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tb_daily_product_summary")
    op.execute("DROP TABLE IF EXISTS tb_daily_checkout_summary")

