from alembic import op
import sqlalchemy as sa

revision = "0023_external_data"
down_revision = "0022_runtime_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_data_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("key_field", sa.String(length=180), nullable=False),
        sa.Column("sync_mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "form_data_source_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("data_source_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(length=120), nullable=False),
        sa.Column("filter_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "bulk_publish_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_template_ids_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bulk_publish_jobs")
    op.drop_table("form_data_source_bindings")
    op.drop_table("external_data_sources")
