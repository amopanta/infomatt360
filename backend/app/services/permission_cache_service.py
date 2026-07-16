"""Cache de permisos efectivos por (usuario, proyecto).

Ver auditoria tecnica de julio 2026, hallazgo E-004: `get_project_permissions`
podia ejecutar hasta 3 queries por chequeo de permiso (asignacion de proyecto,
proyecto, asignacion de organizacion), sin ningun cache -- y se llama en
practicamente cada endpoint de escritura. Sigue el mismo patron memoria/Redis-
opcional que ya usan `ApiKeyProfileCache` (`app/middleware/rate_limit.py`) y
`AuthThrottleService`, para mantenerse consistente el dia que haya varias
replicas del backend (E-001/E-003, aun sin decision de infraestructura).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class CachedProjectAssignment:
    """Sustituto liviano de `UserProjectAssignment` para un hit de cache.

    `approval_flow_service.user_can_execute_step` es el unico llamador de
    `get_project_permissions` que usa el `assignment` devuelto, y solo lee
    `.role_id` -- cachear la fila ORM completa no es seguro (queda separada
    de cualquier sesion futura), asi que se cachea unicamente ese campo.
    """

    role_id: str


CachedEntry = tuple[str | None, frozenset[str]]


class PermissionCacheBackend(Protocol):
    def get(self, user_id: str, project_id: str) -> CachedEntry | None: ...

    def set(self, user_id: str, project_id: str, role_id: str | None, permissions: frozenset[str]) -> None: ...

    def invalidate_user(self, user_id: str) -> None: ...

    def clear(self) -> None: ...


class InMemoryPermissionCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[CachedEntry, float]] = {}
        self._lock = Lock()

    def get(self, user_id: str, project_id: str) -> CachedEntry | None:
        ttl = max(settings.permissions_cache_ttl_seconds, 0)
        if ttl == 0:
            return None
        key = self._key(user_id, project_id)
        now = time.monotonic()
        with self._lock:
            item = self._values.get(key)
            if not item:
                return None
            entry, expires_at = item
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return entry

    def set(self, user_id: str, project_id: str, role_id: str | None, permissions: frozenset[str]) -> None:
        ttl = max(settings.permissions_cache_ttl_seconds, 0)
        if ttl == 0:
            return
        with self._lock:
            self._values[self._key(user_id, project_id)] = ((role_id, permissions), time.monotonic() + ttl)

    def invalidate_user(self, user_id: str) -> None:
        prefix = f"{user_id}:"
        with self._lock:
            for key in [item for item in self._values if item.startswith(prefix)]:
                self._values.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def _key(self, user_id: str, project_id: str) -> str:
        return f"{user_id}:{project_id}"


in_memory_permission_cache = InMemoryPermissionCache()


class RedisPermissionCache:
    """Cache distribuido para cuando haya varias replicas del backend.

    La importacion de redis es diferida para que desarrollo y pruebas puedan
    seguir sin Redis instalado/levantado (mismo patron que RedisRateLimiter).
    """

    _NO_ROLE_MARKER = "\x00"

    def __init__(self, url: str, prefix: str) -> None:
        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover - depende de entorno productivo
            raise RuntimeError("Instale redis para usar PERMISSIONS_CACHE_BACKEND=redis") from exc
        self._redis = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix.rstrip(":")

    def get(self, user_id: str, project_id: str) -> CachedEntry | None:
        raw = self._redis.get(self._key(user_id, project_id))
        if raw is None:
            return None
        role_id_part, _, permissions_part = raw.partition("|")
        role_id = None if role_id_part == self._NO_ROLE_MARKER else role_id_part
        permissions = frozenset(item for item in permissions_part.split(",") if item)
        return (role_id, permissions)

    def set(self, user_id: str, project_id: str, role_id: str | None, permissions: frozenset[str]) -> None:
        ttl = max(settings.permissions_cache_ttl_seconds, 1)
        role_id_part = role_id if role_id is not None else self._NO_ROLE_MARKER
        raw = f"{role_id_part}|{','.join(sorted(permissions))}"
        self._redis.setex(self._key(user_id, project_id), ttl, raw)

    def invalidate_user(self, user_id: str) -> None:
        self._delete_matching(f"{self._prefix}:{user_id}:*")

    def clear(self) -> None:
        self._delete_matching(f"{self._prefix}:*")

    def _delete_matching(self, pattern: str) -> None:
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break

    def _key(self, user_id: str, project_id: str) -> str:
        return f"{self._prefix}:{user_id}:{project_id}"


_distributed_permission_cache: PermissionCacheBackend | None = None


def get_permission_cache() -> PermissionCacheBackend:
    global _distributed_permission_cache
    backend = settings.permissions_cache_backend.lower().strip()
    if backend == "redis":
        if not settings.redis_url:
            return in_memory_permission_cache
        if _distributed_permission_cache is None:
            _distributed_permission_cache = RedisPermissionCache(settings.redis_url, settings.permissions_cache_redis_prefix)
        return _distributed_permission_cache
    return in_memory_permission_cache


def reset_distributed_permission_cache() -> None:
    global _distributed_permission_cache
    _distributed_permission_cache = None


def invalidate_permissions_for_user(user_id: str) -> None:
    get_permission_cache().invalidate_user(user_id)
