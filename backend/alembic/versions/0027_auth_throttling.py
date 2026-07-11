from alembic import op
import sqlalchemy as sa

revision = "0027_auth_throttling"
down_revision = "0026_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_throttles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("action", "identifier_hash", name="uq_auth_throttle_action_identifier"),
    )
    op.create_index("ix_auth_throttles_action", "auth_throttles", ["action"])
    op.create_index("ix_auth_throttles_identifier_hash", "auth_throttles", ["identifier_hash"])
    op.create_index("ix_auth_throttles_blocked_until", "auth_throttles", ["blocked_until"])


def downgrade() -> None:
    op.drop_index("ix_auth_throttles_blocked_until", table_name="auth_throttles")
    op.drop_index("ix_auth_throttles_identifier_hash", table_name="auth_throttles")
    op.drop_index("ix_auth_throttles_action", table_name="auth_throttles")
    op.drop_table("auth_throttles")
