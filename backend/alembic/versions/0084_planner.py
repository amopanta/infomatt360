"""Planeador mensual (docs/144) y coordinador de equipo."""

from alembic import op
import sqlalchemy as sa

revision = "0084_planner"
down_revision = "0083_review_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gestor_teams", sa.Column("coordinator_user_id", sa.String(36), nullable=True))
    op.create_index("ix_gestor_teams_coordinator_user_id", "gestor_teams", ["coordinator_user_id"])
    op.create_table(
        "planner_settings",
        sa.Column("project_id", sa.String(36), primary_key=True),
        sa.Column("count_policy", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("family_key", sa.String(20), nullable=False, server_default="participant"),
        sa.Column("family_field", sa.String(180), nullable=True),
        sa.Column("activity_date_field", sa.String(180), nullable=True),
        sa.Column("municipality_field", sa.String(180), nullable=True),
        sa.Column("timezone", sa.String(60), nullable=False, server_default="America/Bogota"),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "planner_population",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("municipality", sa.String(120), nullable=False),
        sa.Column("families", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "year", "municipality", name="uq_planner_population_scope"),
    )
    op.create_index("ix_planner_population_project_id", "planner_population", ["project_id"])
    op.create_table(
        "planner_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("municipality", sa.String(120), nullable=False, server_default=""),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("gestor_user_id", sa.String(36), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="records"),
        sa.Column("target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "scope_key", name="uq_planner_target_scope"),
    )
    for column in ("project_id", "year", "template_id", "gestor_user_id"):
        op.create_index(f"ix_planner_targets_{column}", "planner_targets", [column])
    op.create_table(
        "planner_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("gestor_user_id", sa.String(36), nullable=False),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("municipality", sa.String(120), nullable=False, server_default=""),
        sa.Column("coordinator_user_id", sa.String(36), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("planned_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("project_id", "gestor_user_id", "template_id"):
        op.create_index(f"ix_planner_plans_{column}", "planner_plans", [column])
    op.create_table(
        "planner_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("previous_json", sa.Text(), nullable=True),
        sa.Column("new_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("client_ref", sa.String(80), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_planner_history_project_id", "planner_history", ["project_id"])
    op.create_index("ix_planner_history_entity_id", "planner_history", ["entity_id"])
    op.create_index("ix_planner_history_client_ref", "planner_history", ["client_ref"])
    op.create_table(
        "planner_cuts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("settings_json", sa.Text(), nullable=False),
        sa.Column("closed_by", sa.String(36), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "year", "month", name="uq_planner_cut_period"),
    )
    op.create_index("ix_planner_cuts_project_id", "planner_cuts", ["project_id"])


def downgrade() -> None:
    for table in ("planner_cuts", "planner_history", "planner_plans", "planner_targets", "planner_population", "planner_settings"):
        op.drop_table(table)
    op.drop_index("ix_gestor_teams_coordinator_user_id", table_name="gestor_teams")
    op.drop_column("gestor_teams", "coordinator_user_id")
