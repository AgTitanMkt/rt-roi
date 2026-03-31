"""creating the product table

Revision ID: ef5cb58dc7db
Revises: d4e5f6a7b8c9
Create Date: 2026-03-31 14:07:47.895659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ef5cb58dc7db'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_tb_metrics_snapshots_id")
    op.execute("DROP TABLE IF EXISTS tb_metrics_snapshots")
    op.execute("ALTER TABLE tb_hourly_metrics ADD COLUMN IF NOT EXISTS product TEXT")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE tb_hourly_metrics DROP COLUMN IF EXISTS product")
    op.create_table('tb_metrics_snapshots',
    sa.Column('id', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('metric_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
    sa.Column('squad', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('cost', sa.NUMERIC(precision=12, scale=2), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('profit', sa.NUMERIC(precision=12, scale=2), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('roi', sa.NUMERIC(precision=8, scale=4), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('revenue', sa.NUMERIC(precision=8, scale=2), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('checkout_conversion', sa.NUMERIC(precision=12, scale=2), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('tb_metrics_snapshots_pkey'))
    )
    op.create_index(op.f('ix_tb_metrics_snapshots_id'), 'tb_metrics_snapshots', ['id'], unique=False)
    # ### end Alembic commands ###
