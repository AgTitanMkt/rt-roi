"""add offer_id to hourly metrics

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-31 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_hourly_metrics') IS NOT NULL THEN
                ALTER TABLE tb_hourly_metrics
                ADD COLUMN IF NOT EXISTS offer_id TEXT;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.tb_hourly_metrics') IS NOT NULL THEN
                ALTER TABLE tb_hourly_metrics
                DROP COLUMN IF EXISTS offer_id;
            END IF;
        END $$;
        """
    )

