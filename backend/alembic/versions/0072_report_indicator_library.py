"""Reusable project indicators for multi-form reports."""

from alembic import op
import sqlalchemy as sa

revision = "0072_report_indicator_library"
down_revision = "0071_builder_response_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_indicators",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "code", name="uq_report_indicator_project_code"),
    )
    op.create_index("ix_report_indicators_project_id", "report_indicators", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_report_indicators_project_id", table_name="report_indicators")
    op.drop_table("report_indicators")
