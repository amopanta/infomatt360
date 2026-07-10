from alembic import op
import sqlalchemy as sa

revision = "0037_bulk_worker_backoff"
down_revision = "0036_bulk_worker_locking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("bulk_import_jobs")}
    indexes = {index["name"] for index in inspector.get_indexes("bulk_import_jobs")}
    if "next_attempt_at" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
    if "ix_bulk_import_jobs_next_attempt_at" not in indexes:
        op.create_index("ix_bulk_import_jobs_next_attempt_at", "bulk_import_jobs", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_bulk_import_jobs_next_attempt_at", table_name="bulk_import_jobs")
    op.drop_column("bulk_import_jobs", "next_attempt_at")
