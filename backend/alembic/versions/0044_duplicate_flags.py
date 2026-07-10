from alembic import op
import sqlalchemy as sa

revision = "0044_duplicate_flags"
down_revision = "0043_manager_qr_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    participant_columns = {column["name"] for column in inspector.get_columns("participants")}
    if "duplicate_flag" not in participant_columns:
        op.add_column("participants", sa.Column("duplicate_flag", sa.String(length=20), nullable=False, server_default="none"))

    record_columns = {column["name"] for column in inspector.get_columns("runtime_records")}
    if "content_hash" not in record_columns:
        op.add_column("runtime_records", sa.Column("content_hash", sa.String(length=64), nullable=True))
        op.create_index("ix_runtime_records_content_hash", "runtime_records", ["content_hash"])
    if "duplicate_flag" not in record_columns:
        op.add_column("runtime_records", sa.Column("duplicate_flag", sa.String(length=20), nullable=False, server_default="none"))


def downgrade() -> None:
    op.drop_column("runtime_records", "duplicate_flag")
    op.drop_index("ix_runtime_records_content_hash", table_name="runtime_records")
    op.drop_column("runtime_records", "content_hash")
    op.drop_column("participants", "duplicate_flag")
