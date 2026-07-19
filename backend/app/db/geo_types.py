"""Tipo de columna de geometria dialect-aware.

En Postgres+PostGIS usa GeoAlchemy2 (columna Geometry real, indexable con
GiST). En cualquier otro dialecto (SQLite en dev/demo/tests) cae a Text,
guardando el mismo string GeoJSON que ya usaba GisFeature.geometry_json --
nadie necesita PostGIS instalado para desarrollar o correr pytest.
"""

from sqlalchemy.types import Text, TypeDecorator


class Geography(TypeDecorator):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from geoalchemy2 import Geometry  # import perezoso: no requerido en SQLite

            return dialect.type_descriptor(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value
