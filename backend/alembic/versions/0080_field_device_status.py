"""Field device status (heartbeat) and gestor route points.

Va después de 0080_case_relations_and_exports (PR #48): ambas partían de 0079.
"""

from alembic import op
import sqlalchemy as sa

revision = "0080_field_device_status"
down_revision = "0080_case_relations_and_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_device_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("device_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("platform", sa.String(60), nullable=False, server_default=""),
        sa.Column("app_version", sa.String(30), nullable=False, server_default=""),
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draft_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("oldest_pending_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("recent_errors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("last_latitude", sa.Float(), nullable=True),
        sa.Column("last_longitude", sa.Float(), nullable=True),
        sa.Column("last_location_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("device_id", "user_id", name="uq_field_device_status_device_user"),
    )
    op.create_index("ix_field_device_status_device_id", "field_device_status", ["device_id"])
    op.create_index("ix_field_device_status_user_id", "field_device_status", ["user_id"])
    op.create_index("ix_field_device_status_project_id", "field_device_status", ["project_id"])
    op.create_table(
        "field_route_points",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("device_id", "user_id", "recorded_at", name="uq_field_route_point"),
    )
    op.create_index("ix_field_route_points_user_id", "field_route_points", ["user_id"])
    op.create_index("ix_field_route_points_project_user_time", "field_route_points", ["project_id", "user_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("field_route_points")
    op.drop_table("field_device_status")
