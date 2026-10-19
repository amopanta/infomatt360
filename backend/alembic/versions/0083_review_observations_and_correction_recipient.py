"""Structured review observations and correction recipient (docs/141)."""

from alembic import op
import sqlalchemy as sa

revision = "0083_review_observations"
down_revision = "0082_field_device_remote_wipe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runtime_records", sa.Column("correction_user_id", sa.String(36), nullable=True))
    op.add_column("runtime_records", sa.Column("returned_at", sa.DateTime(), nullable=True))
    op.create_index("ix_runtime_records_correction_user_id", "runtime_records", ["correction_user_id"])
    op.create_table(
        "review_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("record_id", sa.String(36), nullable=False),
        sa.Column("review_action_id", sa.String(36), nullable=True),
        sa.Column("field_name", sa.String(180), nullable=True),
        sa.Column("repeat_path", sa.String(300), nullable=True),
        sa.Column("evidence_file_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_action", sa.String(300), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("client_ref", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("record_id", "client_ref", name="uq_review_observation_client_ref"),
    )
    for column in ("project_id", "record_id", "review_action_id", "status", "created_by", "created_at"):
        op.create_index(f"ix_review_observations_{column}", "review_observations", [column])


def downgrade() -> None:
    op.drop_table("review_observations")
    op.drop_index("ix_runtime_records_correction_user_id", table_name="runtime_records")
    op.drop_column("runtime_records", "returned_at")
    op.drop_column("runtime_records", "correction_user_id")
