from alembic import op
import sqlalchemy as sa

revision = "0045_excel_import_jobs"
down_revision = "0044_duplicate_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "excel_import_jobs" in inspector.get_table_names():
        return
    op.create_table(
        "excel_import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("source_filename", sa.String(length=250), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("column_mapping_json", sa.Text(), nullable=True),
        sa.Column("preview_json", sa.Text(), nullable=True),
        sa.Column("rows_json", sa.Text(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("failed_rows", sa.Integer(), nullable=False),
        sa.Column("error_report_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_excel_import_jobs_project_id", "excel_import_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_excel_import_jobs_project_id", table_name="excel_import_jobs")
    op.drop_table("excel_import_jobs")
