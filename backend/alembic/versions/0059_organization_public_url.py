from alembic import op
import sqlalchemy as sa

revision = "0059_organization_public_url"
down_revision = "0058_builder_public_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns("organizations")]
    if "public_url" not in columns:
        op.add_column("organizations", sa.Column("public_url", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "public_url")
