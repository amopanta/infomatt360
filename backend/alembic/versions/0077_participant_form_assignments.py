"""Participant, form and responsible-user assignments.

Revision ID: 0077_participant_form_assignments
Revises: 0076_case_territory_saved_exports
"""

from alembic import op
import sqlalchemy as sa

revision = "0077_participant_form_assignments"
down_revision = "0076_case_territory_saved_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participant_form_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("participant_id", sa.String(36), nullable=False),
        sa.Column("responsible_user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assigned_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("template_id", "participant_id", name="uq_participant_form_assignment"),
    )
    for column in ("project_id", "template_id", "participant_id", "responsible_user_id"):
        op.create_index(f"ix_participant_form_assignments_{column}", "participant_form_assignments", [column])


def downgrade() -> None:
    op.drop_table("participant_form_assignments")
