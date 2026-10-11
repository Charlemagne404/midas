"""Add a rolling integrity head for the paper event journal."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("paper_accounts", sa.Column("journal_hash", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("paper_accounts", "journal_hash")
