"""Agregar expires_at a project_api_keys (auditoria tecnica de julio 2026,
hallazgo S-004).

Revision ID: 0065_api_key_expiration
Revises: 0064_excel_import_template_id
"""

from alembic import op
import sqlalchemy as sa

revision = "0065_api_key_expiration"
down_revision = "0064_excel_import_template_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("project_api_keys")}

    if "expires_at" not in columns:
        op.add_column("project_api_keys", sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_api_keys", "expires_at")
