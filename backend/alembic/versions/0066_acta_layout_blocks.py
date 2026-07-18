"""Constructor visual de actas (docs/96 item #4, docs/109): layout_json y
template_id en acta_templates, y html_template pasa a ser nullable.

Revision ID: 0066_acta_layout_blocks
Revises: 0065_api_key_expiration
"""

from alembic import op
import sqlalchemy as sa

revision = "0066_acta_layout_blocks"
down_revision = "0065_api_key_expiration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("acta_templates")}

    if "layout_json" not in columns:
        op.add_column("acta_templates", sa.Column("layout_json", sa.Text(), nullable=True))
    if "template_id" not in columns:
        op.add_column("acta_templates", sa.Column("template_id", sa.String(length=36), nullable=True))
        op.create_index("ix_acta_templates_template_id", "acta_templates", ["template_id"])

    with op.batch_alter_table("acta_templates") as batch_op:
        batch_op.alter_column("html_template", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("acta_templates") as batch_op:
        batch_op.alter_column("html_template", existing_type=sa.Text(), nullable=False)
    op.drop_index("ix_acta_templates_template_id", table_name="acta_templates")
    op.drop_column("acta_templates", "template_id")
    op.drop_column("acta_templates", "layout_json")
