"""Crear tabla de asignaciones usuario-organizacion (rol a nivel organizacion).

Revision ID: 0062_user_organization_assignments
Revises: 0061_runtime_record_participant_link
"""

from alembic import op
import sqlalchemy as sa

revision = "0062_user_organization_assignments"
down_revision = "0061_runtime_record_participant_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_organization_assignments" in inspector.get_table_names():
        return

    op.create_table(
        "user_organization_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_organization_assignments_user_id", "user_organization_assignments", ["user_id"], unique=False)
    op.create_index("ix_user_organization_assignments_organization_id", "user_organization_assignments", ["organization_id"], unique=False)
    op.create_index("ix_user_organization_assignments_role_id", "user_organization_assignments", ["role_id"], unique=False)
    op.create_index("ix_org_assignments_user_org_status", "user_organization_assignments", ["user_id", "organization_id", "status"], unique=False)
    op.create_index("ix_org_assignments_org_status_role", "user_organization_assignments", ["organization_id", "status", "role_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_org_assignments_org_status_role", table_name="user_organization_assignments")
    op.drop_index("ix_org_assignments_user_org_status", table_name="user_organization_assignments")
    op.drop_index("ix_user_organization_assignments_role_id", table_name="user_organization_assignments")
    op.drop_index("ix_user_organization_assignments_organization_id", table_name="user_organization_assignments")
    op.drop_index("ix_user_organization_assignments_user_id", table_name="user_organization_assignments")
    op.drop_table("user_organization_assignments")
