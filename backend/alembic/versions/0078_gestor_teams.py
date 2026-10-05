"""Gestor teams and their independent user/participant memberships."""

from alembic import op
import sqlalchemy as sa

revision = "0078_gestor_teams"
down_revision = "0077_participant_form_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("gestor_teams", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_gestor_team_project_name"))
    op.create_index("ix_gestor_teams_project_id", "gestor_teams", ["project_id"])
    op.create_table("gestor_team_users", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("gestor_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False), sa.UniqueConstraint("team_id", "user_id", name="uq_gestor_team_user"))
    op.create_index("ix_gestor_team_users_team_id", "gestor_team_users", ["team_id"])
    op.create_index("ix_gestor_team_users_user_id", "gestor_team_users", ["user_id"])
    op.create_table("gestor_team_participants", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("gestor_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.String(36), nullable=False),
        sa.UniqueConstraint("team_id", "participant_id", name="uq_gestor_team_participant"))
    op.create_index("ix_gestor_team_participants_team_id", "gestor_team_participants", ["team_id"])
    op.create_index("ix_gestor_team_participants_participant_id", "gestor_team_participants", ["participant_id"])


def downgrade() -> None:
    op.drop_table("gestor_team_participants")
    op.drop_table("gestor_team_users")
    op.drop_table("gestor_teams")
