"""Participant source rules for builder templates."""

from alembic import op
import sqlalchemy as sa

revision = "0073_participant_source"
down_revision = "0072_report_indicator_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("builder_templates", sa.Column("participant_source_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("builder_templates", "participant_source_json")
