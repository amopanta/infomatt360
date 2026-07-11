from __future__ import annotations

import time
from hashlib import sha256
from threading import Lock
from typing import Protocol

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.api_key_service import api_key_service


class RateLimiterBackend(Protocol):
    def check(self, key: str, maximum: int, window_seconds: int) -> tuple[bool, int, int]:
        ...

    def clear(self) -> None:
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = Lock()

    def check(self, key: str, maximum: int, window_seconds: int) -> tuple[bool, int, int]:
        now = time.monotonic()
        floor = now - window_seconds
        with self._lock:
            timestamps = [item for item in self._hits.get(key, []) if item >= floor]
            allowed = len(timestamps) < maximum
            if allowed:
                timestamps.append(now)
            self._hits[key] = timestamps
            remaining = max(maximum - len(timestamps), 0)
            retry_after = int(max(window_seconds - (now - timestamps[0]), 1)) if timestamps else window_seconds
        return allowed, remaining, retry_after

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = InMemoryRateLimiter()


class RedisRateLimiter:
    """Rate limiter distribuido para despliegues con varios workers/replicas.

    Usa Redis solo cuando esta configurado. La importacion es diferida para que
    desarrollo y pruebas puedan seguir sin Redis instalado/levantado.
    """

    def __init__(self, url: str, prefix: str) -> None:
        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover - depende de entorno productivo
            raise RuntimeError("Instale redis para usar API_RATE_LIMIT_BACKEND=redis") from exc
        self._redis = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix.rstrip(":")

    def check(self, key: str, maximum: int, window_seconds: int) -> tuple[bool, int, int]:
        redis_key = f"{self._prefix}:{sha256(key.encode('utf-8')).hexdigest()}"
        current = int(self._redis.incr(redis_key))
        if current == 1:
            self._redis.expire(redis_key, window_seconds)
        ttl = self._redis.ttl(redis_key)
        retry_after = int(ttl if ttl and ttl > 0 else window_seconds)
        allowed = current <= maximum
        remaining = max(maximum - current, 0)
        return allowed, remaining, retry_after

    def clear(self) -> None:
        pattern = f"{self._prefix}:*"
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break


_distributed_rate_limiter: RateLimiterBackend | None = None


def get_rate_limiter() -> RateLimiterBackend:
    global _distributed_rate_limiter
    backend = settings.api_rate_limit_backend.lower().strip()
    if backend == "redis":
        if not settings.redis_url:
            return rate_limiter
        if _distributed_rate_limiter is None:
            _distributed_rate_limiter = RedisRateLimiter(settings.redis_url, settings.api_rate_limit_redis_prefix)
        return _distributed_rate_limiter
    return rate_limiter


def reset_distributed_rate_limiter() -> None:
    global _distributed_rate_limiter
    _distributed_rate_limiter = None


class ApiKeyProfileCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float]] = {}
        self._lock = Lock()

    def get(self, raw_key: str) -> str | None:
        ttl = max(settings.api_key_profile_cache_ttl_seconds, 0)
        if ttl == 0:
            return None
        cache_key = self._cache_key(raw_key)
        now = time.monotonic()
        with self._lock:
            item = self._values.get(cache_key)
            if not item:
                return None
            profile, expires_at = item
            if expires_at <= now:
                self._values.pop(cache_key, None)
                return None
            return profile

    def set(self, raw_key: str, profile: str | None) -> None:
        ttl = max(settings.api_key_profile_cache_ttl_seconds, 0)
        if ttl == 0 or not profile:
            return
        with self._lock:
            self._values[self._cache_key(raw_key)] = (profile, time.monotonic() + ttl)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def _cache_key(self, raw_key: str) -> str:
        return sha256(raw_key.encode("utf-8")).hexdigest()


api_key_profile_cache = ApiKeyProfileCache()


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.api_rate_limit_enabled or self._is_exempt(request.url.path):
            return await call_next(request)

        profile = await self._api_key_profile(request)
        if profile == "trusted_sync":
            response = await call_next(request)
            response.headers["X-RateLimit-Policy"] = "trusted_sync"
            return response

        maximum = max(self._limit_for_profile(profile), 1)
        window_seconds = max(settings.api_rate_limit_window_seconds, 1)
        key = f"{profile or 'ip'}:{self._rate_key_identity(request)}:{request.method}:{request.url.path}"
        limiter = get_rate_limiter()
        allowed, remaining, retry_after = limiter.check(key, maximum, window_seconds)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Intente de nuevo mas tarde."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(maximum),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Backend": self._backend_name(),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(maximum)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Policy"] = profile or "ip"
        response.headers["X-RateLimit-Backend"] = self._backend_name()
        return response

    def _client_ip(self, request: Request) -> str:
        socket_ip = request.client.host if request.client else "unknown"
        trusted_proxies = {item.strip() for item in settings.api_rate_limit_trusted_proxy_ips.split(",") if item.strip()}
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded and socket_ip in trusted_proxies:
            return forwarded.split(",")[0].strip()
        return socket_ip

    def _is_exempt(self, path: str) -> bool:
        return path == "/health" or path.startswith("/api/v1/health")

    async def _api_key_profile(self, request: Request) -> str | None:
        raw_key = request.headers.get("x-api-key")
        if not raw_key:
            return None
        cached = api_key_profile_cache.get(raw_key)
        if cached:
            return cached
        return await run_in_threadpool(self._api_key_profile_from_db, raw_key)

    def _api_key_profile_from_db(self, raw_key: str) -> str | None:
        db = SessionLocal()
        try:
            profile = api_key_service.rate_limit_profile_for_key(db, raw_key)
            api_key_profile_cache.set(raw_key, profile)
            return profile
        finally:
            db.close()

    def _limit_for_profile(self, profile: str | None) -> int:
        if profile == "high_volume":
            return settings.api_rate_limit_high_volume_requests
        if profile == "standard":
            return settings.api_rate_limit_api_key_requests
        return settings.api_rate_limit_requests

    def _rate_key_identity(self, request: Request) -> str:
        raw_key = request.headers.get("x-api-key")
        if raw_key:
            parsed = api_key_service.parse(raw_key)
            if parsed:
                return f"api-key:{parsed.key_id}"
        return self._client_ip(request)

    def _backend_name(self) -> str:
        if settings.api_rate_limit_backend.lower().strip() == "redis" and settings.redis_url:
            return "redis"
        return "memory"
