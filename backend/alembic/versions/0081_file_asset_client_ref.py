"""Client reference on file assets for idempotent re-uploads from field devices."""

from alembic import op
import sqlalchemy as sa

revision = "0081_file_asset_client_ref"
down_revision = "0080_field_device_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("file_assets", sa.Column("client_ref", sa.String(80), nullable=True))
    op.create_index("ix_file_assets_client_ref", "file_assets", ["client_ref"])


def downgrade() -> None:
    op.drop_index("ix_file_assets_client_ref", table_name="file_assets")
    op.drop_column("file_assets", "client_ref")
