"""Persist the per extension Google Search page limit."""

from alembic import op
import sqlalchemy as sa


revision = "0006_max_google_search_pages"
down_revision = "0005_installation_llm_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "installed_extensions",
        sa.Column("max_google_search_pages", sa.Integer(), server_default="10", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("installed_extensions", "max_google_search_pages")
