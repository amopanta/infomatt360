from alembic import op
import sqlalchemy as sa

revision = "0075_participant_import_groups"
down_revision = "0074_form_lookups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("excel_import_jobs", sa.Column("group_name", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("excel_import_jobs", "group_name")
