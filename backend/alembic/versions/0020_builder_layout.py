from alembic import op
import sqlalchemy as sa

revision = "0020_builder_layout"
down_revision = "0019_builder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "builder_pages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("visible", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "builder_sections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("collapsible", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("visible", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "builder_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("responsive", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "builder_columns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("row_id", sa.String(length=36), nullable=False),
        sa.Column("desktop_width", sa.Integer(), nullable=False),
        sa.Column("tablet_width", sa.Integer(), nullable=False),
        sa.Column("mobile_width", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("builder_columns")
    op.drop_table("builder_rows")
    op.drop_table("builder_sections")
    op.drop_table("builder_pages")
