"""Crea storage_profiles, gis_layers y gis_features.

Estas tres tablas existian solo via `Base.metadata.create_all()` (modo
desarrollo/demo) pero nunca tuvieron una migracion Alembic propia -- un
despliegue productivo que solo corriera `alembic upgrade head` (la via
documentada) quedaria sin estas tablas. Se crean aqui de forma idempotente
para no romper bases que ya las tengan por create_all.
"""

from alembic import op
import sqlalchemy as sa

revision = "0047_storage_and_gis_tables"
down_revision = "0046_backup_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "storage_profiles" not in table_names:
        op.create_table(
            "storage_profiles",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("provider", sa.String(length=60), nullable=False),
            sa.Column("base_path", sa.Text(), nullable=True),
            sa.Column("bucket_name", sa.String(length=180), nullable=True),
            sa.Column("endpoint_url", sa.Text(), nullable=True),
            sa.Column("credentials_json", sa.Text(), nullable=True),
            sa.Column("max_file_size_mb", sa.Integer(), nullable=False),
            sa.Column("is_default", sa.String(length=10), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_storage_profiles_project_id", "storage_profiles", ["project_id"])

    if "gis_layers" not in table_names:
        op.create_table(
            "gis_layers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("layer_type", sa.String(length=60), nullable=False),
            sa.Column("style_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gis_layers_project_id", "gis_layers", ["project_id"])

    if "gis_features" not in table_names:
        op.create_table(
            "gis_features",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("layer_id", sa.String(length=36), nullable=True),
            sa.Column("participant_id", sa.String(length=36), nullable=True),
            sa.Column("record_id", sa.String(length=36), nullable=True),
            sa.Column("feature_type", sa.String(length=60), nullable=False),
            sa.Column("latitude", sa.String(length=60), nullable=True),
            sa.Column("longitude", sa.String(length=60), nullable=True),
            sa.Column("geometry_json", sa.Text(), nullable=True),
            sa.Column("properties_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gis_features_project_id", "gis_features", ["project_id"])
        op.create_index("ix_gis_features_layer_id", "gis_features", ["layer_id"])
        op.create_index("ix_gis_features_participant_id", "gis_features", ["participant_id"])
        op.create_index("ix_gis_features_record_id", "gis_features", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_gis_features_record_id", table_name="gis_features")
    op.drop_index("ix_gis_features_participant_id", table_name="gis_features")
    op.drop_index("ix_gis_features_layer_id", table_name="gis_features")
    op.drop_index("ix_gis_features_project_id", table_name="gis_features")
    op.drop_table("gis_features")
    op.drop_index("ix_gis_layers_project_id", table_name="gis_layers")
    op.drop_table("gis_layers")
    op.drop_index("ix_storage_profiles_project_id", table_name="storage_profiles")
    op.drop_table("storage_profiles")
