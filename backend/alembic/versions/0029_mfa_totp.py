from alembic import op
import sqlalchemy as sa

revision = "0029_mfa_totp"
down_revision = "0028_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_hashes", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_last_counter", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_last_counter")
    op.drop_column("users", "mfa_recovery_hashes")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
