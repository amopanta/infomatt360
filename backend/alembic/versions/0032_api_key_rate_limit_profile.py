from alembic import op
import sqlalchemy as sa

revision = "0032_api_key_rate_limit_profile"
down_revision = "0031_project_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_api_keys", sa.Column("rate_limit_profile", sa.String(length=40), nullable=False, server_default="standard"))


def downgrade() -> None:
    op.drop_column("project_api_keys", "rate_limit_profile")
