"""Cache genérico de consultas pesadas con TTL configurable.

Complementa el cache de permisos (permission_cache_service) con un cache
de propósito general para consultas de lectura que son costosas y toleran
datos ligeramente desactualizados:

  - Dashboard / resumen de proyecto (GROUP BY sobre runtime_records)
  - Listado de plantillas por proyecto (consultado en cada carga de pantalla)
  - Conteos de registros por plantilla

Sigue el mismo patrón memoria/Redis-opcional de `permission_cache_service`
y `ApiKeyProfileCache`.  El TTL por defecto es 60 segundos -- suficiente
para absorber ráfagas de recarga en el frontend sin datos demasiado viejos.

Uso típico::

    from app.services.query_cache_service import query_cache

    # En un servicio:
    cache_key = f"project_summary:{project_id}"
    cached = query_cache.get(cache_key)
    if cached is not None:
        return cached
    result = _compute_heavy_summary(db, project_id)
    query_cache.set(cache_key, result)
    return result

    # Al modificar datos que invalidan el cache:
    query_cache.invalidate_prefix(f"project_summary:{project_id}")
"""

from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any

from app.core.config import settings


class InMemoryQueryCache:
    """Cache en memoria con TTL, seguro entre hilos."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        ttl = self._ttl()
        if ttl <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            value, expires_at = item
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl()
        if effective_ttl <= 0:
            return
        with self._lock:
            self._store[key] = (value, time.monotonic() + effective_ttl)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _ttl(self) -> int:
        return getattr(settings, "query_cache_ttl_seconds", 60)


class RedisQueryCache:
    """Cache distribuido sobre Redis, para cuando haya varias réplicas."""

    def __init__(self, url: str, prefix: str = "qcache") -> None:
        try:
            from redis import Redis
        except ImportError as exc:
            raise RuntimeError("Instale redis para usar QUERY_CACHE_BACKEND=redis") from exc
        self._redis = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix.rstrip(":")

    def get(self, key: str) -> Any | None:
        raw = self._redis.get(self._make_key(key))
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else getattr(settings, "query_cache_ttl_seconds", 60)
        if effective_ttl <= 0:
            return
        self._redis.setex(self._make_key(key), effective_ttl, json.dumps(value, default=str))

    def invalidate(self, key: str) -> None:
        self._redis.delete(self._make_key(key))

    def invalidate_prefix(self, prefix: str) -> None:
        pattern = f"{self._prefix}:{prefix}*"
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break

    def clear(self) -> None:
        self.invalidate_prefix("")

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"


_query_cache_instance: InMemoryQueryCache | RedisQueryCache | None = None


def get_query_cache() -> InMemoryQueryCache | RedisQueryCache:
    """Devuelve el singleton del cache de consultas."""
    global _query_cache_instance
    if _query_cache_instance is not None:
        return _query_cache_instance
    backend = getattr(settings, "query_cache_backend", "memory").lower().strip()
    if backend == "redis" and getattr(settings, "redis_url", None):
        _query_cache_instance = RedisQueryCache(
            settings.redis_url,
            getattr(settings, "query_cache_redis_prefix", "qcache"),
        )
    else:
        _query_cache_instance = InMemoryQueryCache()
    return _query_cache_instance


def reset_query_cache() -> None:
    """Reset para pruebas."""
    global _query_cache_instance
    _query_cache_instance = None


# Singleton de acceso rápido
query_cache = InMemoryQueryCache()
