"""GIS real (docs/96 item #8): columna geom dialect-aware en gis_features.

En Postgres+PostGIS agrega una columna Geometry real (GeoAlchemy2) con indice
GiST y crea la extension postgis si falta. En SQLite agrega la misma columna
como TEXT, siguiendo el patron ya usado por geometry_json. Aditiva: no toca
columnas existentes.

Revision ID: 0068_gis_geometry_column
Revises: 0067_report_boards
"""

from alembic import op
import sqlalchemy as sa

revision = "0068_gis_geometry_column"
down_revision = "0067_report_boards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("gis_features")}
    if "geom" in columns:
        return

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        from geoalchemy2 import Geometry

        op.add_column("gis_features", sa.Column("geom", Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True))
        op.execute("CREATE INDEX IF NOT EXISTS ix_gis_features_geom ON gis_features USING GIST (geom)")
    else:
        op.add_column("gis_features", sa.Column("geom", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_gis_features_geom")
    op.drop_column("gis_features", "geom")
