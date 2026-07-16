import pytest

from app.services.permission_cache_service import in_memory_permission_cache


@pytest.fixture(autouse=True)
def _reset_permission_cache():
    """Evita que el cache de permisos (E-004, docs/108) filtre estado entre
    pruebas -- es un singleton a nivel de modulo que persiste durante toda
    la sesion de pytest, y muchas pruebas reutilizan ids fijos por archivo."""
    in_memory_permission_cache.clear()
    yield
    in_memory_permission_cache.clear()
