from alembic import op
import sqlalchemy as sa

revision = "0033_bulk_import_jobs"
down_revision = "0032_api_key_rate_limit_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bulk_import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "template_id", "idempotency_key", name="uq_bulk_import_idempotency"),
    )
    op.create_index("ix_bulk_import_jobs_project_id", "bulk_import_jobs", ["project_id"])
    op.create_index("ix_bulk_import_jobs_template_id", "bulk_import_jobs", ["template_id"])
    op.create_index("ix_bulk_import_jobs_idempotency_key", "bulk_import_jobs", ["idempotency_key"])
    op.create_index("ix_bulk_import_jobs_status", "bulk_import_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bulk_import_jobs_status", table_name="bulk_import_jobs")
    op.drop_index("ix_bulk_import_jobs_idempotency_key", table_name="bulk_import_jobs")
    op.drop_index("ix_bulk_import_jobs_template_id", table_name="bulk_import_jobs")
    op.drop_index("ix_bulk_import_jobs_project_id", table_name="bulk_import_jobs")
    op.drop_table("bulk_import_jobs")
