from alembic import op
import sqlalchemy as sa

revision = "0025_external_data_snapshots"
down_revision = "0024_theme_and_offline_backup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_data_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("data_source_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_external_data_snapshots_data_source_id",
        "external_data_snapshots",
        ["data_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_data_snapshots_data_source_id", table_name="external_data_snapshots")
    op.drop_table("external_data_snapshots")
