"""Crear tabla base de participantes.

Revision ID: 0005_participants_base
Revises: 0004_forms_base
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_participants_base"
down_revision = "0004_forms_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("external_code", sa.String(length=120), nullable=True),
        sa.Column("document_id", sa.String(length=80), nullable=True),
        sa.Column("full_name", sa.String(length=220), nullable=False),
        sa.Column("participant_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_participants_project_id", "participants", ["project_id"], unique=False)
    op.create_index("ix_participants_external_code", "participants", ["external_code"], unique=False)
    op.create_index("ix_participants_document_id", "participants", ["document_id"], unique=False)
    op.create_index("ix_participants_full_name", "participants", ["full_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_participants_full_name", table_name="participants")
    op.drop_index("ix_participants_document_id", table_name="participants")
    op.drop_index("ix_participants_external_code", table_name="participants")
    op.drop_index("ix_participants_project_id", table_name="participants")
    op.drop_table("participants")
