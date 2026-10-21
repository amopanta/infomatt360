"""Conciliación de la base espejo e importación desde bases externas (docs/146)."""

from alembic import op
import sqlalchemy as sa

revision = "0086_db_sync"
down_revision = "0085_user_profile_capturer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mirror_runs", sa.Column("summary_json", sa.Text(), nullable=True))
    op.create_table(
        "db_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("source_table", sa.String(180), nullable=False),
        sa.Column("template_id", sa.String(36), nullable=True),
        sa.Column("mapping_json", sa.Text(), nullable=False),
        sa.Column("key_column", sa.String(180), nullable=False),
        sa.Column("cursor_column", sa.String(180), nullable=True),
        sa.Column("last_cursor", sa.String(120), nullable=True),
        sa.Column("record_status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_db_imports_project_id", "db_imports", ["project_id"])
    op.create_index("ix_db_imports_source_id", "db_imports", ["source_id"])
    op.create_table(
        "db_import_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("import_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("rows_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(80), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_db_import_runs_import_id", "db_import_runs", ["import_id"])
    op.create_table(
        "db_import_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("import_id", sa.String(36), nullable=False),
        sa.Column("source_key", sa.String(200), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("import_id", "source_key", name="uq_db_import_key"),
    )
    op.create_index("ix_db_import_keys_import_id", "db_import_keys", ["import_id"])


def downgrade() -> None:
    for table in ("db_import_keys", "db_import_runs", "db_imports"):
        op.drop_table(table)
    op.drop_column("mirror_runs", "summary_json")
