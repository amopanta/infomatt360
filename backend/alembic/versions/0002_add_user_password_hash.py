"""Agregar hash de contrasena a usuarios.

Revision ID: 0002_add_user_password_hash
Revises: 0001_identity_base
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_user_password_hash"
down_revision = "0001_identity_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False, server_default="CHANGE_ON_FIRST_LOGIN"),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
