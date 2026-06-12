from alembic import op
import sqlalchemy as sa

revision = "0012_integrations"
down_revision = "0011_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "integration_maps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("target_table", sa.String(length=180), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "integration_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("map_id", sa.String(length=36), nullable=True),
        sa.Column("mode", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("integration_jobs")
    op.drop_table("integration_maps")
    op.drop_table("integration_sources")
