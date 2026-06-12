"""Inicializacion controlada de base de datos.

En produccion se usara Alembic. Esta funcion se mantiene para pruebas locales
rapidas y ambientes de desarrollo inicial.
"""

from app.db.base import Base
from app.db.session import engine
from app.models import identity  # noqa: F401  Importa modelos para registrar metadata.


def init_db() -> None:
    """Crea tablas en desarrollo si no existen."""
    Base.metadata.create_all(bind=engine)
