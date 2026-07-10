from alembic import op
import sqlalchemy as sa

revision = "0046_backup_jobs"
down_revision = "0045_excel_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "backup_jobs" in inspector.get_table_names():
        return
    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("storage_profile_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("triggered_by", sa.String(length=36), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_jobs_project_id", "backup_jobs", ["project_id"])
    op.create_index("ix_backup_jobs_storage_profile_id", "backup_jobs", ["storage_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_backup_jobs_storage_profile_id", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_project_id", table_name="backup_jobs")
    op.drop_table("backup_jobs")
