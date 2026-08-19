"""Add controllable processing runs and job states.

Revision ID: 0003_processing_runs
Revises: 0002_extension_overhaul
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_processing_runs"
down_revision = "0002_extension_overhaul"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_runs_installation_id", "processing_runs", ["installation_id"])
    op.add_column("job_analysis", sa.Column("processing_run_id", sa.String(length=64), nullable=True))
    op.add_column("job_analysis", sa.Column("processing_status", sa.String(length=32), server_default="pending", nullable=False))
    op.create_index("ix_job_analysis_processing_run_id", "job_analysis", ["processing_run_id"])


def downgrade() -> None:
    op.drop_index("ix_job_analysis_processing_run_id", table_name="job_analysis")
    op.drop_column("job_analysis", "processing_status")
    op.drop_column("job_analysis", "processing_run_id")
    op.drop_index("ix_processing_runs_installation_id", table_name="processing_runs")
    op.drop_table("processing_runs")
