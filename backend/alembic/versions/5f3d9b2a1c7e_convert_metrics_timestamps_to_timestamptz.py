"""convert metrics timestamps to timestamptz

Revision ID: 5f3d9b2a1c7e
Revises: 0dc63c4bc11b
Create Date: 2026-03-26 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f3d9b2a1c7e"
down_revision: Union[str, Sequence[str], None] = "0dc63c4bc11b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing metric_at values are Sao Paulo wall time stored as naive timestamp.
    # Convert them to timezone-aware values preserving local meaning.
    op.alter_column(
        "tb_metrics_snapshots",
        "metric_at",
        existing_type=sa.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
        postgresql_using="metric_at AT TIME ZONE 'America/Sao_Paulo'",
    )

    # created_at historically follows server time; treat legacy values as UTC.
    op.alter_column(
        "tb_metrics_snapshots",
        "created_at",
        existing_type=sa.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "tb_metrics_snapshots",
        "created_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=sa.TIMESTAMP(),
        existing_nullable=True,
        existing_server_default=sa.text("now()"),
        postgresql_using="timezone('UTC', created_at)",
    )

    op.alter_column(
        "tb_metrics_snapshots",
        "metric_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=sa.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="timezone('America/Sao_Paulo', metric_at)",
    )

