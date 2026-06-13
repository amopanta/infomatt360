from alembic import op
import sqlalchemy as sa

revision = "0024_theme_and_offline_backup"
down_revision = "0023_external_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_themes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("program_name", sa.String(length=180), nullable=False),
        sa.Column("icon_name", sa.String(length=120), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=False),
        sa.Column("secondary_color", sa.String(length=20), nullable=False),
        sa.Column("background_color", sa.String(length=20), nullable=False),
        sa.Column("custom_css", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "template_theme_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("theme_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "offline_backup_imports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=120), nullable=True),
        sa.Column("file_name", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "offline_backup_record_checks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("backup_import_id", sa.String(length=36), nullable=False),
        sa.Column("local_record_id", sa.String(length=180), nullable=False),
        sa.Column("server_record_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("offline_backup_record_checks")
    op.drop_table("offline_backup_imports")
    op.drop_table("template_theme_bindings")
    op.drop_table("form_themes")
