"""Store WebAuthn public credentials and form verification events."""

from alembic import op
import sqlalchemy as sa

revision = "0079_device_verification"
down_revision = "0078_gestor_teams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("credential_id", sa.String(512), nullable=False, unique=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_device_credentials_user_id", "device_credentials", ["user_id"])
    op.create_table(
        "device_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("component_id", sa.String(36), nullable=False),
        sa.Column("challenge", sa.String(128), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("credential_id", sa.String(512), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_record_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_device_verifications_user_id", "device_verifications", ["user_id"])
    op.create_index("ix_device_verifications_template_id", "device_verifications", ["template_id"])


def downgrade() -> None:
    op.drop_table("device_verifications")
    op.drop_table("device_credentials")
