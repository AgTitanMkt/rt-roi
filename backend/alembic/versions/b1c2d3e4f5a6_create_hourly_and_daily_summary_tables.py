"""create hourly and daily summary tables

Revision ID: b1c2d3e4f5a6
Revises: f53e3a2f1094
Create Date: 2026-03-30 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "f53e3a2f1094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_hourly_metrics (
            campaign_id TEXT NOT NULL,
            metric_at TIMESTAMPTZ NOT NULL,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            squad TEXT NOT NULL DEFAULT 'unknown',
            cost NUMERIC(12,2) DEFAULT 0,
            profit NUMERIC(12,2) DEFAULT 0,
            roi NUMERIC(8,4) DEFAULT 0,
            revenue NUMERIC(8,2) DEFAULT 0,
            CONSTRAINT pk_tb_hourly_metrics PRIMARY KEY (campaign_id, metric_at)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tb_daily_metrics_summary (
            metric_date DATE NOT NULL,
            squad TEXT NOT NULL,
            checkout_conversion NUMERIC(12,2) DEFAULT 0,
            cost NUMERIC(12,2) DEFAULT 0,
            profit NUMERIC(12,2) DEFAULT 0,
            roi NUMERIC(8,4) DEFAULT 0,
            revenue NUMERIC(8,2) DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT pk_tb_daily_metrics_summary PRIMARY KEY (metric_date, squad)
        )
        """
    )

    # Backfill da tabela horaria a partir do snapshot legado, quando existir.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_metrics_snapshots') IS NOT NULL THEN
                INSERT INTO tb_hourly_metrics (
                    campaign_id,
                    metric_at,
                    checkout_conversion,
                    created_at,
                    squad,
                    cost,
                    profit,
                    roi,
                    revenue
                )
                SELECT
                    id::text,
                    metric_at,
                    COALESCE(checkout_conversion, 0),
                    created_at,
                    COALESCE(squad, 'unknown'),
                    COALESCE(cost, 0),
                    COALESCE(profit, 0),
                    COALESCE(roi, 0),
                    COALESCE(revenue, 0)
                FROM tb_metrics_snapshots
                ON CONFLICT (campaign_id, metric_at)
                DO UPDATE SET
                    checkout_conversion = EXCLUDED.checkout_conversion,
                    squad = EXCLUDED.squad,
                    cost = EXCLUDED.cost,
                    profit = EXCLUDED.profit,
                    roi = EXCLUDED.roi,
                    revenue = EXCLUDED.revenue;
            END IF;
        END $$;
        """
    )

    # Backfill da tabela de summary diario.
    op.execute(
        """
        INSERT INTO tb_daily_metrics_summary (
            metric_date,
            squad,
            checkout_conversion,
            cost,
            profit,
            roi,
            revenue,
            updated_at
        )
        SELECT
            timezone('America/Sao_Paulo', metric_at)::date AS metric_date,
            COALESCE(squad, 'unknown') AS squad,
            COALESCE(SUM(checkout_conversion), 0) AS checkout_conversion,
            COALESCE(SUM(cost), 0) AS cost,
            COALESCE(SUM(profit), 0) AS profit,
            ROUND(COALESCE(SUM(profit), 0) / NULLIF(COALESCE(SUM(cost), 0), 0), 4) AS roi,
            COALESCE(SUM(revenue), 0) AS revenue,
            now() AS updated_at
        FROM tb_hourly_metrics
        GROUP BY metric_date, squad
        ON CONFLICT (metric_date, squad)
        DO UPDATE SET
            checkout_conversion = EXCLUDED.checkout_conversion,
            cost = EXCLUDED.cost,
            profit = EXCLUDED.profit,
            roi = EXCLUDED.roi,
            revenue = EXCLUDED.revenue,
            updated_at = now();
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tb_daily_metrics_summary")
    op.execute("DROP TABLE IF EXISTS tb_hourly_metrics")

