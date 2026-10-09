"""Add typed parent/child cases and case snapshots to existing modules."""

from alembic import op
import sqlalchemy as sa

revision = "0080_case_relations_and_exports"
down_revision = "0079_device_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participant_cases", sa.Column("case_type", sa.String(80), nullable=False, server_default="general"))
    op.add_column("participant_cases", sa.Column("parent_case_id", sa.String(36), nullable=True))
    op.create_index("ix_participant_cases_case_type", "participant_cases", ["case_type"])
    op.create_index("ix_participant_cases_parent_case_id", "participant_cases", ["parent_case_id"])
    op.add_column("saved_exports", sa.Column("export_kind", sa.String(20), nullable=False, server_default="summary"))
    op.execute("UPDATE saved_exports SET export_kind = 'form' WHERE template_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("saved_exports", "export_kind")
    op.drop_index("ix_participant_cases_parent_case_id", table_name="participant_cases")
    op.drop_index("ix_participant_cases_case_type", table_name="participant_cases")
    op.drop_column("participant_cases", "parent_case_id")
    op.drop_column("participant_cases", "case_type")
