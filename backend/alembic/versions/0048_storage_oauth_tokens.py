from alembic import op
import sqlalchemy as sa

revision = "0048_storage_oauth_tokens"
down_revision = "0047_storage_and_gis_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("storage_profiles")}
    if "oauth_tokens_encrypted" not in columns:
        op.add_column("storage_profiles", sa.Column("oauth_tokens_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("storage_profiles", "oauth_tokens_encrypted")
