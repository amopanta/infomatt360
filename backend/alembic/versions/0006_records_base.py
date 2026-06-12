"""Crear tablas base de registros.

Revision ID: 0006_records_base
Revises: 0005_participants_base
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_records_base"
down_revision = "0005_participants_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("participant_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_channel", sa.String(length=40), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_records_project_id", "records", ["project_id"], unique=False)
    op.create_index("ix_records_form_id", "records", ["form_id"], unique=False)
    op.create_index("ix_records_participant_id", "records", ["participant_id"], unique=False)
    op.create_index("ix_records_created_by", "records", ["created_by"], unique=False)
    op.create_index("ix_records_updated_by", "records", ["updated_by"], unique=False)

    op.create_table(
        "record_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_record_events_record_id", "record_events", ["record_id"], unique=False)
    op.create_index("ix_record_events_user_id", "record_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_record_events_user_id", table_name="record_events")
    op.drop_index("ix_record_events_record_id", table_name="record_events")
    op.drop_table("record_events")
    op.drop_index("ix_records_updated_by", table_name="records")
    op.drop_index("ix_records_created_by", table_name="records")
    op.drop_index("ix_records_participant_id", table_name="records")
    op.drop_index("ix_records_form_id", table_name="records")
    op.drop_index("ix_records_project_id", table_name="records")
    op.drop_table("records")
