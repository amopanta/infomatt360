"""Sesion y motor de base de datos.

Este modulo centraliza la conexion a base de datos. En desarrollo puede usar
SQLite, pero la arquitectura objetivo es PostgreSQL con migraciones Alembic.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# SQLite necesita este parametro para funcionar correctamente con TestClient.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Entrega una sesion por solicitud HTTP y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
