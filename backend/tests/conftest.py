import os
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.permission_cache_service import in_memory_permission_cache
from app.services.query_cache_service import query_cache


@pytest.fixture(autouse=True)
def _reset_permission_cache():
    """Evita que el cache de permisos (E-004, docs/108) filtre estado entre
    pruebas -- es un singleton a nivel de modulo que persiste durante toda
    la sesion de pytest, y muchas pruebas reutilizan ids fijos por archivo."""
    in_memory_permission_cache.clear()
    yield
    in_memory_permission_cache.clear()


@pytest.fixture(autouse=True)
def _reset_query_cache():
    """Evita que el cache de consultas filtre estado entre pruebas."""
    query_cache.clear()
    yield
    query_cache.clear()


@pytest.fixture(autouse=True, scope="session")
def _ensure_upload_directory():
    """Crea el directorio de uploads si no existe para que los health-checks
    y el asistente de instalacion no fallen por infraestructura ausente en
    entornos de CI/sandbox donde solo hay SQLite en memoria."""
    upload_path = Path(settings.upload_directory)
    upload_path.mkdir(parents=True, exist_ok=True)
    yield
    # No eliminamos: otros procesos pueden necesitarlo aun.
