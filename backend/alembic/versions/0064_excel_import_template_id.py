"""Agregar template_id a excel_import_jobs para la carga masiva de registros
historicos por Excel (ver docs/104).

Revision ID: 0064_excel_import_template_id
Revises: 0063_mirror_runs
"""

from alembic import op
import sqlalchemy as sa

revision = "0064_excel_import_template_id"
down_revision = "0063_mirror_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("excel_import_jobs")}

    if "template_id" not in columns:
        op.add_column("excel_import_jobs", sa.Column("template_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("excel_import_jobs", "template_id")
