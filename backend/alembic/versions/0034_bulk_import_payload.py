from alembic import op
import sqlalchemy as sa

revision = "0034_bulk_import_payload"
down_revision = "0033_bulk_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bulk_import_jobs", sa.Column("payload_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bulk_import_jobs", "payload_json")
