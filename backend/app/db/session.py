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


def engine_options(database_url: str) -> dict[str, object]:
    options: dict[str, object] = {"connect_args": {"check_same_thread": False} if database_url.startswith("sqlite") else {}}
    if not database_url.startswith("sqlite"):
        options.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": settings.db_pool_recycle_seconds,
            "pool_pre_ping": True,
        }
        )
    return options


engine = create_engine(settings.database_url, **engine_options(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Entrega una sesion por solicitud HTTP y la cierra al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
