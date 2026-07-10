from alembic import op
import sqlalchemy as sa

revision = "0039_template_theme_json"
down_revision = "0038_approval_flow_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("builder_templates")}
    if "theme_json" not in columns:
        op.add_column("builder_templates", sa.Column("theme_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("builder_templates", "theme_json")
