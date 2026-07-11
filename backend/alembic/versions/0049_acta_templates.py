from alembic import op
import sqlalchemy as sa

revision = "0049_acta_templates"
down_revision = "0048_storage_oauth_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "acta_templates" in inspector.get_table_names():
        return
    op.create_table(
        "acta_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("html_template", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_acta_templates_project_id", "acta_templates", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_acta_templates_project_id", table_name="acta_templates")
    op.drop_table("acta_templates")
