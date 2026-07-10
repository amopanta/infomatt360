from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import ApiRateLimitMiddleware, api_key_profile_cache, get_rate_limiter, rate_limiter, reset_distributed_rate_limiter


def test_api_rate_limit_returns_429_after_threshold() -> None:
    original_enabled = settings.api_rate_limit_enabled
    original_requests = settings.api_rate_limit_requests
    original_window = settings.api_rate_limit_window_seconds
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_requests = 2
    settings.api_rate_limit_window_seconds = 60
    rate_limiter.clear()
    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.10"})
            second = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.10"})
            third = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.10"})

            assert first.status_code == 401
            assert first.headers["X-RateLimit-Limit"] == "2"
            assert first.headers["X-RateLimit-Backend"] == "memory"
            assert second.status_code == 401
            assert third.status_code == 429
            assert third.headers["Retry-After"]
            assert third.headers["X-RateLimit-Backend"] == "memory"
            assert third.json()["detail"].startswith("Demasiadas solicitudes")
    finally:
        settings.api_rate_limit_enabled = original_enabled
        settings.api_rate_limit_requests = original_requests
        settings.api_rate_limit_window_seconds = original_window
        rate_limiter.clear()
        api_key_profile_cache.clear()


def test_health_endpoints_are_exempt_from_rate_limit() -> None:
    original_enabled = settings.api_rate_limit_enabled
    original_requests = settings.api_rate_limit_requests
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_requests = 1
    rate_limiter.clear()
    try:
        with TestClient(app) as client:
            responses = [client.get("/api/v1/health/", headers={"X-Forwarded-For": "203.0.113.11"}) for _ in range(3)]
            assert [response.status_code for response in responses] == [200, 200, 200]
            assert all("X-RateLimit-Limit" not in response.headers for response in responses)
    finally:
        settings.api_rate_limit_enabled = original_enabled
        settings.api_rate_limit_requests = original_requests
        rate_limiter.clear()
        api_key_profile_cache.clear()


def test_rate_limit_ignores_spoofed_forwarded_for_without_trusted_proxy() -> None:
    original_enabled = settings.api_rate_limit_enabled
    original_requests = settings.api_rate_limit_requests
    original_window = settings.api_rate_limit_window_seconds
    original_trusted = settings.api_rate_limit_trusted_proxy_ips
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_requests = 2
    settings.api_rate_limit_window_seconds = 60
    settings.api_rate_limit_trusted_proxy_ips = ""
    rate_limiter.clear()
    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.20"})
            second = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.21"})
            third = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.22"})

            assert first.status_code == 401
            assert second.status_code == 401
            assert third.status_code == 429
    finally:
        settings.api_rate_limit_enabled = original_enabled
        settings.api_rate_limit_requests = original_requests
        settings.api_rate_limit_window_seconds = original_window
        settings.api_rate_limit_trusted_proxy_ips = original_trusted
        rate_limiter.clear()


def test_rate_limit_accepts_forwarded_for_from_trusted_proxy() -> None:
    original_enabled = settings.api_rate_limit_enabled
    original_requests = settings.api_rate_limit_requests
    original_window = settings.api_rate_limit_window_seconds
    original_trusted = settings.api_rate_limit_trusted_proxy_ips
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_requests = 2
    settings.api_rate_limit_window_seconds = 60
    settings.api_rate_limit_trusted_proxy_ips = "testclient"
    rate_limiter.clear()
    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.30"})
            second = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.31"})
            third = client.get("/api/v1/auth/session", headers={"X-Forwarded-For": "203.0.113.32"})

            assert first.status_code == 401
            assert second.status_code == 401
            assert third.status_code == 401
    finally:
        settings.api_rate_limit_enabled = original_enabled
        settings.api_rate_limit_requests = original_requests
        settings.api_rate_limit_window_seconds = original_window
        settings.api_rate_limit_trusted_proxy_ips = original_trusted
        rate_limiter.clear()


def test_redis_backend_without_url_falls_back_to_memory() -> None:
    original_backend = settings.api_rate_limit_backend
    original_redis_url = settings.redis_url
    settings.api_rate_limit_backend = "redis"
    settings.redis_url = ""
    reset_distributed_rate_limiter()
    try:
        assert get_rate_limiter() is rate_limiter
    finally:
        settings.api_rate_limit_backend = original_backend
        settings.redis_url = original_redis_url
        reset_distributed_rate_limiter()


def test_api_key_profile_lookup_uses_profile_for_rate_policy(monkeypatch) -> None:
    original_enabled = settings.api_rate_limit_enabled
    original_requests = settings.api_rate_limit_high_volume_requests
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_high_volume_requests = 1234
    rate_limiter.clear()
    api_key_profile_cache.clear()

    calls: list[str] = []

    def fake_profile_lookup(_self: ApiRateLimitMiddleware, raw_key: str) -> str:
        calls.append(raw_key)
        return "high_volume"

    monkeypatch.setattr(ApiRateLimitMiddleware, "_api_key_profile_from_db", fake_profile_lookup)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/session", headers={"X-API-Key": "im360_testkey_testsecret"})

            assert response.status_code == 401
            assert response.headers["X-RateLimit-Policy"] == "high_volume"
            assert response.headers["X-RateLimit-Limit"] == "1234"
            assert calls == ["im360_testkey_testsecret"]
    finally:
        settings.api_rate_limit_enabled = original_enabled
        settings.api_rate_limit_high_volume_requests = original_requests
        rate_limiter.clear()
        api_key_profile_cache.clear()
