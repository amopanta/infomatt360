from alembic import op
import sqlalchemy as sa

revision = "0014_mirror"
down_revision = "0013_etl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mirror_targets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("engine", sa.String(length=60), nullable=False),
        sa.Column("conn_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "mirror_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("tables_json", sa.Text(), nullable=False),
        sa.Column("schedule_mode", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mirror_plans")
    op.drop_table("mirror_targets")
