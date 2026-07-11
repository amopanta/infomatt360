"""Utilidades temporales consistentes para persistencia UTC."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Retorna UTC sin zona para columnas SQLAlchemy DateTime existentes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
