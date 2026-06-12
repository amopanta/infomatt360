"""Base declarativa de SQLAlchemy.

Todos los modelos ORM deben heredar de esta base para que Alembic pueda
identificar cambios y generar migraciones.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
