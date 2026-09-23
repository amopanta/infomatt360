"""CSV lookup attachments used by XLSForm pulldata()."""

from alembic import op
import sqlalchemy as sa

revision = "0074_form_lookups"
down_revision = "0073_participant_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_lookups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("columns_json", sa.Text(), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("template_id", "name", name="uq_form_lookup_template_name"),
    )
    op.create_index("ix_form_lookups_template_id", "form_lookups", ["template_id"])
    op.create_index("ix_form_lookups_project_id", "form_lookups", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_form_lookups_project_id", table_name="form_lookups")
    op.drop_index("ix_form_lookups_template_id", table_name="form_lookups")
    op.drop_table("form_lookups")
