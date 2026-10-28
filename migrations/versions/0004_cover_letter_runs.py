"""Add controllable cover-letter generation runs and job states."""

from alembic import op
import sqlalchemy as sa


revision = "0004_cover_letter_runs"
down_revision = "0003_processing_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cover_letter_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cover_letter_runs_installation_id", "cover_letter_runs", ["installation_id"])
    op.add_column("job_analysis", sa.Column("cover_letter_run_id", sa.String(length=64), nullable=True))
    op.add_column("job_analysis", sa.Column("cover_letter_status", sa.String(length=32), server_default="pending", nullable=False))
    op.add_column("job_analysis", sa.Column("cover_letter_error", sa.Text(), nullable=True))
    op.create_index("ix_job_analysis_cover_letter_run_id", "job_analysis", ["cover_letter_run_id"])


def downgrade() -> None:
    op.drop_index("ix_job_analysis_cover_letter_run_id", table_name="job_analysis")
    op.drop_column("job_analysis", "cover_letter_error")
    op.drop_column("job_analysis", "cover_letter_status")
    op.drop_column("job_analysis", "cover_letter_run_id")
    op.drop_index("ix_cover_letter_runs_installation_id", table_name="cover_letter_runs")
    op.drop_table("cover_letter_runs")
