"""Crear persistencia Runtime.

Revision ID: 0022_runtime_records
Revises: 0021_builder_component_column
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_runtime_records"
down_revision = "0021_builder_component_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("submitted_by", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=120), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "runtime_record_values",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=True),
        sa.Column("field_name", sa.String(length=180), nullable=False),
        sa.Column("field_value_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_record_values")
    op.drop_table("runtime_records")
