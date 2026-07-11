from alembic import op
import sqlalchemy as sa

revision = "0054_governance_support_emergency"
down_revision = "0053_ai_audit_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "emergency_access_keys" not in existing_tables:
        op.create_table(
            "emergency_access_keys",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("issued_by", sa.String(length=36), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=True),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_emergency_access_keys_project_id", "emergency_access_keys", ["project_id"])
        op.create_index("ix_emergency_access_keys_user_id", "emergency_access_keys", ["user_id"])
        op.create_index("ix_emergency_access_keys_issued_by", "emergency_access_keys", ["issued_by"])
        op.create_index("ix_emergency_access_keys_code_hash", "emergency_access_keys", ["code_hash"], unique=True)
        op.create_index("ix_emergency_access_keys_expires_at", "emergency_access_keys", ["expires_at"])

    if "support_tickets" not in existing_tables:
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("subject", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("resolution_channel", sa.String(length=20), nullable=False),
            sa.Column("matched_rule", sa.String(length=60), nullable=True),
            sa.Column("auto_response_text", sa.Text(), nullable=True),
            sa.Column("resolved_by", sa.String(length=36), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_support_tickets_project_id", "support_tickets", ["project_id"])
        op.create_index("ix_support_tickets_created_by", "support_tickets", ["created_by"])
        op.create_index("ix_support_tickets_status", "support_tickets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_created_by", table_name="support_tickets")
    op.drop_index("ix_support_tickets_project_id", table_name="support_tickets")
    op.drop_table("support_tickets")

    op.drop_index("ix_emergency_access_keys_expires_at", table_name="emergency_access_keys")
    op.drop_index("ix_emergency_access_keys_code_hash", table_name="emergency_access_keys")
    op.drop_index("ix_emergency_access_keys_issued_by", table_name="emergency_access_keys")
    op.drop_index("ix_emergency_access_keys_user_id", table_name="emergency_access_keys")
    op.drop_index("ix_emergency_access_keys_project_id", table_name="emergency_access_keys")
    op.drop_table("emergency_access_keys")
