from alembic import op
import sqlalchemy as sa

revision = "0052_integration_donor_sync"
down_revision = "0051_whatsapp_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    source_columns = {column["name"] for column in inspector.get_columns("integration_sources")}
    if "credentials_encrypted" not in source_columns:
        op.add_column("integration_sources", sa.Column("credentials_encrypted", sa.Text(), nullable=True))

    map_columns = {column["name"] for column in inspector.get_columns("integration_maps")}
    if "template_id" not in map_columns:
        op.add_column("integration_maps", sa.Column("template_id", sa.String(length=36), nullable=True))
        op.create_index("ix_integration_maps_template_id", "integration_maps", ["template_id"])

    job_columns = {column["name"] for column in inspector.get_columns("integration_jobs")}
    if "reference_record_id" not in job_columns:
        op.add_column("integration_jobs", sa.Column("reference_record_id", sa.String(length=36), nullable=True))
        op.create_index("ix_integration_jobs_reference_record_id", "integration_jobs", ["reference_record_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_jobs_reference_record_id", table_name="integration_jobs")
    op.drop_column("integration_jobs", "reference_record_id")

    op.drop_index("ix_integration_maps_template_id", table_name="integration_maps")
    op.drop_column("integration_maps", "template_id")

    op.drop_column("integration_sources", "credentials_encrypted")
