"""add checkout_type to hourly metrics

Revision ID: d4e5f6a7b8c9
Revises: b1c2d3e4f5a6
Create Date: 2026-03-31 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_hourly_metrics') IS NULL THEN
                RETURN;
            END IF;

            ALTER TABLE tb_hourly_metrics
            ADD COLUMN IF NOT EXISTS checkout_type TEXT;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_hourly_metrics') IS NULL THEN
                RETURN;
            END IF;

            ALTER TABLE tb_hourly_metrics
            DROP COLUMN IF EXISTS checkout_type;
        END $$;
        """
    )

