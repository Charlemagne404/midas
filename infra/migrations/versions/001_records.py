"""Initial immutable research records."""

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("received_ts_ms", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    for name in ("kind", "source", "received_ts_ms"):
        op.create_index(f"ix_records_{name}", "records", [name])
    op.create_index("ix_records_kind_received", "records", ["kind", "received_ts_ms"])


def downgrade():
    op.drop_table("records")
