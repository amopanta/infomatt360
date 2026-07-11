from alembic import op
import sqlalchemy as sa

revision = "0055_device_asset_lock_and_field_tokens"
down_revision = "0054_governance_support_emergency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "locked_device_fingerprint" not in columns:
        op.add_column("users", sa.Column("locked_device_fingerprint", sa.String(length=200), nullable=True))
    if "device_lock_updated_at" not in columns:
        op.add_column("users", sa.Column("device_lock_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "device_lock_updated_at")
    op.drop_column("users", "locked_device_fingerprint")
