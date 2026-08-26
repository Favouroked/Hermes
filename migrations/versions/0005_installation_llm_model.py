"""Persist a preferred LLM model per installed extension."""
from alembic import op
import sqlalchemy as sa


revision = "0005_installation_llm_model"
down_revision = "0004_cover_letter_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("installed_extensions", sa.Column("llm_model", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("installed_extensions", "llm_model")
