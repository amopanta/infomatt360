"""Add optional response window to builder forms."""

from alembic import op
import sqlalchemy as sa

revision = "0071_builder_response_window"
down_revision = "0070_builder_publication_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("builder_templates")}
    if "starts_at" not in columns:
        op.add_column("builder_templates", sa.Column("starts_at", sa.DateTime(), nullable=True))
    if "ends_at" not in columns:
        op.add_column("builder_templates", sa.Column("ends_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("builder_templates", "ends_at")
    op.drop_column("builder_templates", "starts_at")
