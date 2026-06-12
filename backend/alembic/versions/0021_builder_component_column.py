from alembic import op
import sqlalchemy as sa

revision = "0021_builder_component_column"
down_revision = "0020_builder_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("builder_components", sa.Column("column_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("builder_components", "column_id")
