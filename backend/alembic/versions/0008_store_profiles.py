from alembic import op
import sqlalchemy as sa

revision = "0008_store_profiles"
down_revision = "0007_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("base_path", sa.Text(), nullable=True),
        sa.Column("bucket_name", sa.String(length=180), nullable=True),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("max_size_mb", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("store_profiles")
