"""Crear tabla de asignaciones usuario proyecto.

Revision ID: 0003_user_project_assignments
Revises: 0002_add_user_password_hash
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_user_project_assignments"
down_revision = "0002_add_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_project_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assignments_user_id", "user_project_assignments", ["user_id"], unique=False)
    op.create_index("ix_assignments_project_id", "user_project_assignments", ["project_id"], unique=False)
    op.create_index("ix_assignments_role_id", "user_project_assignments", ["role_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assignments_role_id", table_name="user_project_assignments")
    op.drop_index("ix_assignments_project_id", table_name="user_project_assignments")
    op.drop_index("ix_assignments_user_id", table_name="user_project_assignments")
    op.drop_table("user_project_assignments")
