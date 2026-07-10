from alembic import op
import sqlalchemy as sa

revision = "0038_approval_flow_versioning"
down_revision = "0037_bulk_worker_backoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    flow_columns = {column["name"] for column in inspector.get_columns("approval_flows")}
    if "flow_version" not in flow_columns:
        op.add_column("approval_flows", sa.Column("flow_version", sa.Integer(), nullable=False, server_default="1"))

    review_columns = {column["name"] for column in inspector.get_columns("review_actions")}
    review_indexes = {index["name"] for index in inspector.get_indexes("review_actions")}
    if "approval_flow_id" not in review_columns:
        op.add_column("review_actions", sa.Column("approval_flow_id", sa.String(length=36), nullable=True))
    if "approval_flow_version" not in review_columns:
        op.add_column("review_actions", sa.Column("approval_flow_version", sa.Integer(), nullable=True))
    if "ix_review_actions_approval_flow_id" not in review_indexes:
        op.create_index("ix_review_actions_approval_flow_id", "review_actions", ["approval_flow_id"])

    runtime_columns = {column["name"] for column in inspector.get_columns("runtime_records")}
    runtime_indexes = {index["name"] for index in inspector.get_indexes("runtime_records")}
    if "approval_flow_id" not in runtime_columns:
        op.add_column("runtime_records", sa.Column("approval_flow_id", sa.String(length=36), nullable=True))
    if "approval_flow_version" not in runtime_columns:
        op.add_column("runtime_records", sa.Column("approval_flow_version", sa.String(length=20), nullable=True))
    if "approval_flow_snapshot_json" not in runtime_columns:
        op.add_column("runtime_records", sa.Column("approval_flow_snapshot_json", sa.Text(), nullable=True))
    if "ix_runtime_records_approval_flow_id" not in runtime_indexes:
        op.create_index("ix_runtime_records_approval_flow_id", "runtime_records", ["approval_flow_id"])


def downgrade() -> None:
    op.drop_index("ix_review_actions_approval_flow_id", table_name="review_actions")
    op.drop_index("ix_runtime_records_approval_flow_id", table_name="runtime_records")
    op.drop_column("runtime_records", "approval_flow_snapshot_json")
    op.drop_column("runtime_records", "approval_flow_version")
    op.drop_column("runtime_records", "approval_flow_id")
    op.drop_column("review_actions", "approval_flow_version")
    op.drop_column("review_actions", "approval_flow_id")
    op.drop_column("approval_flows", "flow_version")
