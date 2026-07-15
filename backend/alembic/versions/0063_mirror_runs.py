"""Crear tabla de historial de corridas de sincronizacion de Base Espejo.

Revision ID: 0063_mirror_runs
Revises: 0062_user_organization_assignments
"""

from alembic import op
import sqlalchemy as sa

revision = "0063_mirror_runs"
down_revision = "0062_user_organization_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "mirror_runs" in inspector.get_table_names():
        return

    op.create_table(
        "mirror_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("records_synced", sa.Integer(), nullable=False),
        sa.Column("values_synced", sa.Integer(), nullable=False),
        sa.Column("triggered_by", sa.String(length=36), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mirror_runs_plan_id", "mirror_runs", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mirror_runs_plan_id", table_name="mirror_runs")
    op.drop_table("mirror_runs")
