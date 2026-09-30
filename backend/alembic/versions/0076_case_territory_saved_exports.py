from alembic import op
import sqlalchemy as sa

revision = "0076_case_territory_saved_exports"
down_revision = "0075_participant_import_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("participant_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("participant_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assigned_user_id", sa.String(36)),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("properties_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    for name in ("project_id", "participant_id", "assigned_user_id"):
        op.create_index(f"ix_participant_cases_{name}", "participant_cases", [name])
    op.create_table("case_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("from_user_id", sa.String(36), nullable=False),
        sa.Column("to_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"])
    op.create_table("user_territories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("department", sa.String(120), nullable=False),
        sa.Column("municipality", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", "department", "municipality", name="uq_user_territory"))
    for name in ("project_id", "user_id"):
        op.create_index(f"ix_user_territories_{name}", "user_territories", [name])
    op.create_table("saved_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("template_id", sa.String(36)),
        sa.Column("frequency", sa.String(30), nullable=False),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        sa.Column("last_run_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_saved_exports_project_id", "saved_exports", ["project_id"])
    op.create_table("saved_export_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("export_id", sa.String(36), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_saved_export_files_export_id", "saved_export_files", ["export_id"])


def downgrade() -> None:
    for table in ("saved_export_files", "saved_exports", "user_territories", "case_events", "participant_cases"):
        op.drop_table(table)
