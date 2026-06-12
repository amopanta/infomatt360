"""Crear tablas base de formularios.

Revision ID: 0004_forms_base
Revises: 0003_user_project_assignments
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_forms_base"
down_revision = "0003_user_project_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_forms_project_id", "forms", ["project_id"], unique=False)
    op.create_index("ix_forms_name", "forms", ["name"], unique=False)

    op.create_table(
        "form_fields",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=250), nullable=False),
        sa.Column("field_type", sa.String(length=60), nullable=False),
        sa.Column("required", sa.String(length=10), nullable=False),
        sa.Column("layout_row", sa.Integer(), nullable=False),
        sa.Column("layout_col", sa.Integer(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("rules_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_form_fields_form_id", "form_fields", ["form_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_form_fields_form_id", table_name="form_fields")
    op.drop_table("form_fields")
    op.drop_index("ix_forms_name", table_name="forms")
    op.drop_index("ix_forms_project_id", table_name="forms")
    op.drop_table("forms")
