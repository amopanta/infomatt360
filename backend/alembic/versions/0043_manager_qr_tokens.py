from alembic import op
import sqlalchemy as sa

revision = "0043_manager_qr_tokens"
down_revision = "0042_installation_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "manager_qr_tokens" in inspector.get_table_names():
        return
    op.create_table(
        "manager_qr_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_manager_qr_tokens_token_hash"),
    )
    op.create_index("ix_manager_qr_tokens_project_id", "manager_qr_tokens", ["project_id"])
    op.create_index("ix_manager_qr_tokens_user_id", "manager_qr_tokens", ["user_id"])
    op.create_index("ix_manager_qr_tokens_token_hash", "manager_qr_tokens", ["token_hash"])
    op.create_index("ix_manager_qr_tokens_expires_at", "manager_qr_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_manager_qr_tokens_expires_at", table_name="manager_qr_tokens")
    op.drop_index("ix_manager_qr_tokens_token_hash", table_name="manager_qr_tokens")
    op.drop_index("ix_manager_qr_tokens_user_id", table_name="manager_qr_tokens")
    op.drop_index("ix_manager_qr_tokens_project_id", table_name="manager_qr_tokens")
    op.drop_table("manager_qr_tokens")
