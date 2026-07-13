from alembic import op
import sqlalchemy as sa

revision = "0060_runtime_record_parent_link"
down_revision = "0059_organization_public_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runtime_records")}

    if "parent_record_id" not in columns:
        op.add_column("runtime_records", sa.Column("parent_record_id", sa.String(length=36), nullable=True))
    if "parent_field_name" not in columns:
        op.add_column("runtime_records", sa.Column("parent_field_name", sa.String(length=180), nullable=True))

    existing_indexes = {index["name"] for index in inspector.get_indexes("runtime_records")}
    if "ix_runtime_records_parent_record_id" not in existing_indexes:
        op.create_index("ix_runtime_records_parent_record_id", "runtime_records", ["parent_record_id"])


def downgrade() -> None:
    op.drop_index("ix_runtime_records_parent_record_id", table_name="runtime_records")
    op.drop_column("runtime_records", "parent_field_name")
    op.drop_column("runtime_records", "parent_record_id")
