"""Pruebas iniciales del backend.

Estas pruebas garantizan que la aplicacion arranca y que los endpoints de
salud responden correctamente. Son la base para integracion continua.
"""

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.main import create_app
from app.core.config import settings
from app.api.v1 import health as health_module
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User
from app.services.metrics_service import metrics_service

client = TestClient(app)


def setup_metrics_permission_context(role_permissions: str):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="metrics-user", full_name="Metrics User", document_id="metrics-doc", email="metrics@example.com")
        role = Role(id="metrics-role", name="Metrics Role", permissions=role_permissions)
        project = Project(id="metrics-project", name="Metrics Project", status="active")
        db.add_all([
            user,
            role,
            project,
            UserProjectAssignment(user_id=user.id, project_id=project.id, role_id=role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="metrics-user")
    return engine


def test_root_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_v1_health() -> None:
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_api_v1_readiness_checks_database() -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert "redis" in data["checks"]
    assert "redis_required" in data["checks"]
    assert data["checks"]["uploads_directory_status"] == "ok"
    assert "cors_allowed_origins" in data["checks"]
    assert "auto_create_tables" in data["checks"]
    assert "trusted_proxy_ips" in data["checks"]
    assert "rate_limit_backend" in data["checks"]
    assert "redis_configured" in data["checks"]
    assert "auth_throttle_backend" in data["checks"]
    assert "api_key_profile_cache_ttl_seconds" in data["checks"]
    assert "request_logging_enabled" in data["checks"]
    assert "request_id_header" in data["checks"]
    assert "metrics_enabled" in data["checks"]
    assert "security_headers_enabled" in data["checks"]
    assert "content_security_policy" in data["checks"]
    assert isinstance(data["warnings"], list)


def test_api_v1_readiness_marks_redis_ok_when_required(monkeypatch) -> None:
    original_rate_backend = settings.api_rate_limit_backend
    original_auth_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    settings.api_rate_limit_backend = "redis"
    settings.auth_throttle_backend = "db"
    settings.redis_url = "redis://example.test:6379/0"
    monkeypatch.setattr(health_module, "_redis_health_check", lambda: ("ok", None))
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        settings.api_rate_limit_backend = original_rate_backend
        settings.auth_throttle_backend = original_auth_backend
        settings.redis_url = original_redis_url

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["redis_required"] is True


def test_api_v1_readiness_fails_when_production_requires_redis_without_url() -> None:
    original_environment = settings.environment
    original_rate_backend = settings.api_rate_limit_backend
    original_auth_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    settings.environment = "production"
    settings.api_rate_limit_backend = "redis"
    settings.auth_throttle_backend = "db"
    settings.redis_url = ""
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        settings.environment = original_environment
        settings.api_rate_limit_backend = original_rate_backend
        settings.auth_throttle_backend = original_auth_backend
        settings.redis_url = original_redis_url

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["redis"] == "not_configured"
    assert any("REDIS_URL" in warning for warning in data["warnings"])


def test_api_v1_readiness_fails_when_production_upload_directory_is_missing(tmp_path) -> None:
    original_environment = settings.environment
    original_upload_directory = settings.upload_directory
    settings.environment = "production"
    settings.upload_directory = str(tmp_path / "missing-uploads")
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        settings.environment = original_environment
        settings.upload_directory = original_upload_directory

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["uploads_directory_status"] == "missing"
    assert any("UPLOAD_DIRECTORY" in warning for warning in data["warnings"])


def test_cors_allows_configured_frontend_origin() -> None:
    response = client.options(
        "/api/v1/health/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_allows_localhost_ip_frontend_origin() -> None:
    response = client.options(
        "/api/v1/health/",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_allows_and_exposes_request_id_header() -> None:
    preflight = client.options(
        "/api/v1/health/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )
    response = client.get("/api/v1/health/", headers={"Origin": "http://localhost:5173"})

    assert preflight.status_code == 200
    assert "X-Request-ID" in preflight.headers["access-control-allow-headers"]
    assert response.status_code == 200
    assert response.headers["access-control-expose-headers"] == "X-Request-ID"


def test_request_id_header_is_returned_and_can_be_provided() -> None:
    response = client.get("/api/v1/health/", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-123"


def test_security_headers_are_returned_on_api_responses() -> None:
    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in response.headers["permissions-policy"]
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_docs_skip_content_security_policy_to_preserve_swagger_ui() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in response.headers


def test_invalid_request_id_header_is_replaced() -> None:
    response = client.get("/api/v1/health/", headers={"X-Request-ID": "bad value with spaces"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "bad value with spaces"
    assert response.headers["x-request-id"]


def test_health_metrics_collect_http_status_and_latency() -> None:
    metrics_service.reset()
    first = client.get("/api/v1/health/")
    second = client.get("/api/v1/auth/session")
    engine = setup_metrics_permission_context("integrations.api_keys.manage")
    try:
        response = client.get("/api/v1/health/metrics")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

    assert first.status_code == 200
    assert second.status_code == 401
    assert response.status_code == 200
    data = response.json()
    assert data["metrics_enabled"] is True
    assert data["http"]["total_requests"] >= 2
    assert data["http"]["by_status_family"]["2xx"] >= 1
    assert data["http"]["by_status_family"]["4xx"] >= 1
    assert data["http"]["by_status_code"]["401"] >= 1
    assert data["http"]["avg_duration_ms"] >= 0
    assert data["http"]["latency_percentiles_ms"]["p50"] >= 0
    assert data["http"]["latency_percentiles_ms"]["p95"] >= data["http"]["latency_percentiles_ms"]["p50"]
    assert data["http"]["latency_percentiles_ms"]["p99"] >= data["http"]["latency_percentiles_ms"]["p95"]
    assert "/api/v1/auth/session" in data["http"]["by_path"]
    assert data["http"]["by_path"]["/api/v1/auth/session"]["latency_percentiles_ms"]["p95"] >= 0
    assert "bulk_jobs" in data
    assert "worker_cycles" in data["bulk_jobs"]


def test_health_metrics_requires_authenticated_user() -> None:
    response = client.get("/api/v1/health/metrics")

    assert response.status_code == 401


def test_health_metrics_requires_operational_permission() -> None:
    engine = setup_metrics_permission_context("records.read")
    try:
        response = client.get("/api/v1/health/metrics")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

    assert response.status_code == 403


def test_health_metrics_prometheus_export() -> None:
    metrics_service.reset()
    client.get("/api/v1/health/")
    engine = setup_metrics_permission_context("integrations.api_keys.manage")
    try:
        response = client.get("/api/v1/health/metrics/prometheus")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "infomatt360_http_requests_total" in response.text
    assert "infomatt360_http_request_duration_ms" in response.text
    assert "infomatt360_bulk_jobs_total" in response.text


def test_health_metrics_prometheus_requires_authenticated_user() -> None:
    response = client.get("/api/v1/health/metrics/prometheus")

    assert response.status_code == 401


def test_production_startup_rejects_insecure_defaults() -> None:
    original_environment = settings.environment
    original_debug = settings.debug
    original_secret = settings.secret_key
    original_auto_create = settings.auto_create_tables
    original_database = settings.database_url
    original_cors = settings.cors_allowed_origins
    original_frontend = settings.frontend_url
    original_refresh_secure = settings.refresh_cookie_secure
    original_refresh_samesite = settings.refresh_cookie_samesite
    original_rate_limit_enabled = settings.api_rate_limit_enabled
    original_rate_limit_backend = settings.api_rate_limit_backend
    original_auth_throttle_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    original_request_logging = settings.request_logging_enabled
    original_metrics = settings.metrics_enabled
    original_security_headers = settings.security_headers_enabled
    original_upload_directory = settings.upload_directory
    settings.environment = "production"
    settings.debug = True
    settings.secret_key = "CHANGE_ME_IN_PRODUCTION"
    settings.auto_create_tables = True
    settings.database_url = "sqlite:///./bad.db"
    settings.cors_allowed_origins = "http://app.insegura.test,*"
    settings.frontend_url = "http://app.insegura.test"
    settings.refresh_cookie_secure = False
    settings.refresh_cookie_samesite = "none"
    settings.api_rate_limit_enabled = False
    settings.api_rate_limit_backend = "redis"
    settings.auth_throttle_backend = "redis"
    settings.redis_url = ""
    settings.request_logging_enabled = False
    settings.metrics_enabled = False
    settings.security_headers_enabled = False
    settings.upload_directory = "./missing-production-uploads"
    try:
        try:
            create_app()
            assert False, "create_app debio fallar con configuracion insegura de produccion"
        except RuntimeError as exc:
            message = str(exc)
            assert "Configuracion insegura para produccion" in message
            assert "REFRESH_COOKIE_SECURE" in message
            assert "REDIS_URL" in message
            assert "METRICS_ENABLED" in message
            assert "FRONTEND_URL" in message
            assert "origenes CORS" in message
            assert "UPLOAD_DIRECTORY" in message
    finally:
        settings.environment = original_environment
        settings.debug = original_debug
        settings.secret_key = original_secret
        settings.auto_create_tables = original_auto_create
        settings.database_url = original_database
        settings.cors_allowed_origins = original_cors
        settings.frontend_url = original_frontend
        settings.refresh_cookie_secure = original_refresh_secure
        settings.refresh_cookie_samesite = original_refresh_samesite
        settings.api_rate_limit_enabled = original_rate_limit_enabled
        settings.api_rate_limit_backend = original_rate_limit_backend
        settings.auth_throttle_backend = original_auth_throttle_backend
        settings.redis_url = original_redis_url
        settings.request_logging_enabled = original_request_logging
        settings.metrics_enabled = original_metrics
        settings.security_headers_enabled = original_security_headers
        settings.upload_directory = original_upload_directory


def test_production_startup_accepts_minimum_secure_configuration(tmp_path) -> None:
    original_environment = settings.environment
    original_debug = settings.debug
    original_secret = settings.secret_key
    original_auto_create = settings.auto_create_tables
    original_database = settings.database_url
    original_cors = settings.cors_allowed_origins
    original_frontend = settings.frontend_url
    original_refresh_secure = settings.refresh_cookie_secure
    original_refresh_samesite = settings.refresh_cookie_samesite
    original_rate_limit_enabled = settings.api_rate_limit_enabled
    original_rate_limit_backend = settings.api_rate_limit_backend
    original_auth_throttle_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    original_request_logging = settings.request_logging_enabled
    original_metrics = settings.metrics_enabled
    original_security_headers = settings.security_headers_enabled
    original_upload_directory = settings.upload_directory
    settings.environment = "production"
    settings.debug = False
    settings.secret_key = "x" * 40
    settings.auto_create_tables = False
    settings.database_url = "postgresql+psycopg2://user:pass@db.internal:5432/infomatt360"
    settings.cors_allowed_origins = "https://app.infomatt360.test"
    settings.frontend_url = "https://app.infomatt360.test"
    settings.refresh_cookie_secure = True
    settings.refresh_cookie_samesite = "strict"
    settings.api_rate_limit_enabled = True
    settings.api_rate_limit_backend = "redis"
    settings.auth_throttle_backend = "redis"
    settings.redis_url = "redis://redis.internal:6379/0"
    settings.request_logging_enabled = True
    settings.metrics_enabled = True
    settings.security_headers_enabled = True
    settings.upload_directory = str(tmp_path)
    try:
        created = create_app()
    finally:
        settings.environment = original_environment
        settings.debug = original_debug
        settings.secret_key = original_secret
        settings.auto_create_tables = original_auto_create
        settings.database_url = original_database
        settings.cors_allowed_origins = original_cors
        settings.frontend_url = original_frontend
        settings.refresh_cookie_secure = original_refresh_secure
        settings.refresh_cookie_samesite = original_refresh_samesite
        settings.api_rate_limit_enabled = original_rate_limit_enabled
        settings.api_rate_limit_backend = original_rate_limit_backend
        settings.auth_throttle_backend = original_auth_throttle_backend
        settings.redis_url = original_redis_url
        settings.request_logging_enabled = original_request_logging
        settings.metrics_enabled = original_metrics
        settings.security_headers_enabled = original_security_headers
        settings.upload_directory = original_upload_directory

    assert created.title == settings.app_name
