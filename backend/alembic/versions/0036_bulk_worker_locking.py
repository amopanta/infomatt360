from alembic import op
import sqlalchemy as sa

revision = "0036_bulk_worker_locking"
down_revision = "0035_assignment_composite_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("bulk_import_jobs")}
    indexes = {index["name"] for index in inspector.get_indexes("bulk_import_jobs")}

    if "worker_id" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("worker_id", sa.String(length=120), nullable=True))
    if "locked_at" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("locked_at", sa.DateTime(), nullable=True))
    if "attempt_count" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    if "max_attempts" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    if "last_error" not in columns:
        op.add_column("bulk_import_jobs", sa.Column("last_error", sa.Text(), nullable=True))
    if "ix_bulk_import_jobs_worker_id" not in indexes:
        op.create_index("ix_bulk_import_jobs_worker_id", "bulk_import_jobs", ["worker_id"])
    if "ix_bulk_import_jobs_locked_at" not in indexes:
        op.create_index("ix_bulk_import_jobs_locked_at", "bulk_import_jobs", ["locked_at"])


def downgrade() -> None:
    op.drop_index("ix_bulk_import_jobs_locked_at", table_name="bulk_import_jobs")
    op.drop_index("ix_bulk_import_jobs_worker_id", table_name="bulk_import_jobs")
    op.drop_column("bulk_import_jobs", "last_error")
    op.drop_column("bulk_import_jobs", "max_attempts")
    op.drop_column("bulk_import_jobs", "attempt_count")
    op.drop_column("bulk_import_jobs", "locked_at")
    op.drop_column("bulk_import_jobs", "worker_id")
