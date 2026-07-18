"""Constructor visual de reportes/tableros (docs/96 item #6, docs/111):
tabla report_boards, uno por proyecto.

Revision ID: 0067_report_boards
Revises: 0066_acta_layout_blocks
"""

from alembic import op
import sqlalchemy as sa

revision = "0067_report_boards"
down_revision = "0066_acta_layout_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "report_boards" in inspector.get_table_names():
        return

    op.create_table(
        "report_boards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("widgets_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_report_boards_project_id", "report_boards", ["project_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_report_boards_project_id", table_name="report_boards")
    op.drop_table("report_boards")
