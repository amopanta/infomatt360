"""Track form ownership, editing, and explicit publication."""

from alembic import op
import sqlalchemy as sa

revision = "0070_builder_publication_metadata"
down_revision = "0069_external_mail_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("builder_templates")}
    if "updated_at" not in columns:
        op.add_column("builder_templates", sa.Column("updated_at", sa.DateTime(), nullable=True))
    if "published_at" not in columns:
        op.add_column("builder_templates", sa.Column("published_at", sa.DateTime(), nullable=True))
    if "created_by" not in columns:
        op.add_column("builder_templates", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.execute("UPDATE builder_templates SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_column("builder_templates", "created_by")
    op.drop_column("builder_templates", "published_at")
    op.drop_column("builder_templates", "updated_at")
