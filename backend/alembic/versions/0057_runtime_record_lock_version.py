from alembic import op
import sqlalchemy as sa

revision = "0057_runtime_record_lock_version"
down_revision = "0056_review_rejected_field_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runtime_records")}

    if "lock_version" not in columns:
        op.add_column("runtime_records", sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("runtime_records", "lock_version")
