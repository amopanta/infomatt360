from alembic import op
import sqlalchemy as sa

revision = "0016_reports"
down_revision = "0015_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("report_type", sa.String(length=80), nullable=False),
        sa.Column("query_json", sa.Text(), nullable=False),
        sa.Column("layout_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "report_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=120), nullable=False),
        sa.Column("access_mode", sa.String(length=40), nullable=False),
        sa.Column("allow_download", sa.String(length=10), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_links")
    op.drop_table("reports")
