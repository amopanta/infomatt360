from alembic import op
import sqlalchemy as sa

revision = "0056_review_rejected_field_name"
down_revision = "0055_device_asset_lock_and_field_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("review_actions")}

    if "rejected_field_name" not in columns:
        op.add_column("review_actions", sa.Column("rejected_field_name", sa.String(length=180), nullable=True))


def downgrade() -> None:
    op.drop_column("review_actions", "rejected_field_name")
