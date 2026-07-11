from alembic import op
import sqlalchemy as sa

revision = "0030_approval_flows"
down_revision = "0029_mfa_totp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_flows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_flows_project_id", "approval_flows", ["project_id"])
    op.create_index("ix_approval_flows_template_id", "approval_flows", ["template_id"])
    op.create_index("ix_approval_flows_status", "approval_flows", ["status"])

    op.create_table(
        "approval_flow_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("flow_id", sa.String(length=36), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("action_label", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("status_after", sa.String(length=60), nullable=False),
        sa.Column("required_permission", sa.String(length=120), nullable=False),
        sa.Column("approver_user_id", sa.String(length=36), nullable=True),
        sa.Column("approver_role_id", sa.String(length=36), nullable=True),
        sa.Column("require_all", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_flow_steps_flow_id", "approval_flow_steps", ["flow_id"])
    op.create_index("ix_approval_flow_steps_approver_user_id", "approval_flow_steps", ["approver_user_id"])
    op.create_index("ix_approval_flow_steps_approver_role_id", "approval_flow_steps", ["approver_role_id"])
    op.create_index("ix_approval_flow_steps_status", "approval_flow_steps", ["status"])


def downgrade() -> None:
    op.drop_index("ix_approval_flow_steps_status", table_name="approval_flow_steps")
    op.drop_index("ix_approval_flow_steps_approver_role_id", table_name="approval_flow_steps")
    op.drop_index("ix_approval_flow_steps_approver_user_id", table_name="approval_flow_steps")
    op.drop_index("ix_approval_flow_steps_flow_id", table_name="approval_flow_steps")
    op.drop_table("approval_flow_steps")
    op.drop_index("ix_approval_flows_status", table_name="approval_flows")
    op.drop_index("ix_approval_flows_template_id", table_name="approval_flows")
    op.drop_index("ix_approval_flows_project_id", table_name="approval_flows")
    op.drop_table("approval_flows")
