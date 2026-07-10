from alembic import op

revision = "0035_assignment_composite_indexes"
down_revision = "0034_bulk_import_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_assignments_user_project_status",
        "user_project_assignments",
        ["user_id", "project_id", "status"],
    )
    op.create_index(
        "ix_assignments_project_status_role",
        "user_project_assignments",
        ["project_id", "status", "role_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_assignments_project_status_role", table_name="user_project_assignments")
    op.drop_index("ix_assignments_user_project_status", table_name="user_project_assignments")
