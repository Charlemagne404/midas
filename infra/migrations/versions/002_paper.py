"""Durable paper accounts and append-only atomic event journal."""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
    )
    op.create_table(
        "paper_events",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(160), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("command", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("previous_checksum", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_paper_event_revision", "paper_events", ["account_id", "revision"], unique=True
    )


def downgrade():
    op.drop_table("paper_events")
    op.drop_table("paper_accounts")
