"""Create the initial Hermes database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("company", sa.String(length=256), nullable=True),
        sa.Column("salary", sa.String(length=256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("page_text", sa.Text(), nullable=True),
        sa.Column("expired", sa.Boolean(), nullable=False),
        sa.Column("has_error", sa.Boolean(), nullable=False),
        sa.Column("is_processing", sa.Boolean(), nullable=False),
        sa.Column("is_processed", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_agent_processed", sa.Boolean(), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_analysis_id", "job_analysis", ["id"], unique=False)

    op.create_table(
        "application_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_analysis_id", sa.Integer(), nullable=False),
        sa.Column("question_html", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_execution_code", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_analysis_id"], ["job_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_questions_id", "application_questions", ["id"], unique=False)

    op.create_table(
        "application_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_analysis_id", sa.Integer(), nullable=False),
        sa.Column("question_html", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("query_selector", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_analysis_id"], ["job_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_actions_id", "application_actions", ["id"], unique=False)

    op.create_table(
        "job_google_search_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("site", sa.String(length=32), nullable=False),
        sa.Column("role_focus", sa.String(length=256), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("google_search_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_google_search_queries_id", "job_google_search_queries", ["id"], unique=False)

    op.create_table(
        "installed_extensions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("resume", sa.Text(), nullable=False),
        sa.Column("preferences", sa.Text(), nullable=False),
        sa.Column("openai_key", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(length=32), server_default="ollama", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_installed_extensions_id", "installed_extensions", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_installed_extensions_id", table_name="installed_extensions")
    op.drop_table("installed_extensions")
    op.drop_index("ix_job_google_search_queries_id", table_name="job_google_search_queries")
    op.drop_table("job_google_search_queries")
    op.drop_index("ix_application_actions_id", table_name="application_actions")
    op.drop_table("application_actions")
    op.drop_index("ix_application_questions_id", table_name="application_questions")
    op.drop_table("application_questions")
    op.drop_index("ix_job_analysis_id", table_name="job_analysis")
    op.drop_table("job_analysis")
