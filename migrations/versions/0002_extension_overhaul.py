"""Add extension workflow state and settings.

Revision ID: 0002_extension_overhaul
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_extension_overhaul"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("cutoff_date", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_runs_installation_id", "search_runs", ["installation_id"])
    op.add_column("job_google_search_queries", sa.Column("search_run_id", sa.String(length=64), nullable=True))
    op.add_column("installed_extensions", sa.Column("auto_fill", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("installed_extensions", "auto_fill")
    op.drop_column("job_google_search_queries", "search_run_id")
    op.drop_index("ix_search_runs_installation_id", table_name="search_runs")
    op.drop_table("search_runs")
