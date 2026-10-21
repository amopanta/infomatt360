"""Remote wipe request and confirmation for field devices."""

from alembic import op
import sqlalchemy as sa

revision = "0082_field_device_remote_wipe"
down_revision = "0081_file_asset_client_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("field_device_status", sa.Column("wipe_requested_at", sa.DateTime(), nullable=True))
    op.add_column("field_device_status", sa.Column("wipe_requested_by", sa.String(36), nullable=True))
    op.add_column("field_device_status", sa.Column("wipe_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("field_device_status", "wipe_completed_at")
    op.drop_column("field_device_status", "wipe_requested_by")
    op.drop_column("field_device_status", "wipe_requested_at")
