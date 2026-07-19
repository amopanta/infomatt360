"""Utilidades temporales consistentes para persistencia UTC."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Retorna UTC sin zona para columnas SQLAlchemy DateTime existentes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Normaliza a UTC sin zona, igual que utc_now() (columnas SQLAlchemy
    DateTime existentes). Un datetime que llega de un query param o de un
    payload del cliente suele venir con sufijo "Z" (consciente de zona);
    compararlo directo contra utc_now() o una columna DateTime naive lanza
    TypeError -- normalizar siempre con esto antes de filtrar/comparar."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
