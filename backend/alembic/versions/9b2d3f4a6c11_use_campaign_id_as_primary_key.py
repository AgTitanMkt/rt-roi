"""use campaign id as primary key

Revision ID: 9b2d3f4a6c11
Revises: 3e1274766ca9
Create Date: 2026-03-30 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b2d3f4a6c11"
down_revision: Union[str, Sequence[str], None] = "3e1274766ca9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tb_metrics_snapshots",
        "id",
        existing_type=sa.Integer(),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using="id::text",
        existing_server_default=sa.text("nextval('tb_metrics_snapshots_id_seq'::regclass)"),
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "tb_metrics_snapshots",
        "id",
        existing_type=sa.Text(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="NULLIF(regexp_replace(id, '[^0-9]', '', 'g'), '')::integer",
        server_default=sa.text("nextval('tb_metrics_snapshots_id_seq'::regclass)"),
    )

