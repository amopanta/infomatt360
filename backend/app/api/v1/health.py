"""Endpoints de salud del sistema.

Estos endpoints sirven para validar que el backend esta vivo y que la API
versionada responde correctamente.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission
from app.core.config import settings
from app.core.permissions import METRICS_VIEW_PERMISSIONS
from app.db.session import get_db
from app.models.identity import User
from app.services.metrics_service import metrics_service

router = APIRouter()


def _requires_redis() -> bool:
    return settings.api_rate_limit_backend.lower().strip() == "redis" or settings.auth_throttle_backend.lower().strip() == "redis"


def _redis_health_check() -> tuple[str, str | None]:
    if not _requires_redis():
        return "not_required", None
    if not settings.redis_url:
        return "not_configured", "Redis esta requerido pero REDIS_URL no esta configurado"
    try:
        from redis import Redis

        Redis.from_url(settings.redis_url, decode_responses=True).ping()
        return "ok", None
    except Exception as exc:  # pragma: no cover - depende de red/servicio externo
        return "error", f"Redis no responde: {exc}"


def _upload_directory_health_check() -> tuple[str, str | None]:
    upload_path = Path(settings.upload_directory)
    if not upload_path.exists():
        return "missing", f"UPLOAD_DIRECTORY no existe: {settings.upload_directory}"
    if not upload_path.is_dir():
        return "error", f"UPLOAD_DIRECTORY no es un directorio: {settings.upload_directory}"
    probe = upload_path / ".infomatt360-healthcheck"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return "ok", None
    except Exception as exc:  # pragma: no cover - depende de permisos del sistema operativo
        return "error", f"UPLOAD_DIRECTORY no permite escritura: {exc}"


def require_metrics_viewer(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    require_any_permission(db, current_user.id, METRICS_VIEW_PERMISSIONS)
    return current_user


@router.get("/", summary="Estado de salud de la API")
def health() -> dict[str, str]:
    """Retorna el estado basico de la API.

    En siguientes versiones este endpoint podra incluir estado de base de datos,
    Redis, MinIO, workers y almacenamiento externo.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready", summary="Preparacion operativa de la API")
def readiness(db: Session = Depends(get_db)) -> dict[str, object]:
    """Valida dependencias minimas para operar o presentar una demo.

    A diferencia del health basico, este endpoint toca la base de datos y
    entrega advertencias de configuracion que deben resolverse antes de
    produccion.
    """
    db.execute(text("SELECT 1")).scalar_one()
    warnings: list[str] = []
    if settings.secret_key == "CHANGE_ME_IN_PRODUCTION" or settings.secret_key.startswith("change-this"):
        warnings.append("SECRET_KEY usa un valor de desarrollo")
    if settings.database_url.startswith("sqlite") and settings.environment.lower() in {"production", "prod"}:
        warnings.append("SQLite no debe usarse como base principal en produccion")
    if settings.environment.lower() in {"production", "prod"} and settings.auto_create_tables:
        warnings.append("AUTO_CREATE_TABLES debe estar desactivado en produccion; usar Alembic")
    if settings.environment.lower() in {"production", "prod"} and not settings.cors_allowed_origins:
        warnings.append("CORS_ALLOWED_ORIGINS debe configurarse explicitamente en produccion")
    if "*" in settings.cors_allowed_origins:
        warnings.append("CORS no debe permitir comodin * en produccion")
    if settings.environment.lower() in {"production", "prod"} and not settings.api_rate_limit_trusted_proxy_ips:
        warnings.append("X-Forwarded-For sera ignorado porque no hay proxies confiables configurados")
    if not settings.smtp_host:
        warnings.append("SMTP no configurado; recuperacion de contrasena solo registra token en logs/dev")
    redis_status, redis_error = _redis_health_check()
    if redis_error:
        warnings.append(redis_error)
    upload_status, upload_error = _upload_directory_health_check()
    if upload_error:
        warnings.append(upload_error)
    is_production = settings.environment.lower() in {"production", "prod"}
    is_ready = (
        redis_status != "error"
        and upload_status == "ok"
        and not (is_production and redis_status == "not_configured")
    )
    payload: dict[str, Any] = {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {
            "database": "ok",
            "redis": redis_status,
            "redis_required": _requires_redis(),
            "uploads_directory": settings.upload_directory,
            "uploads_directory_status": upload_status,
            "frontend_url": settings.frontend_url,
            "cors_allowed_origins": settings.cors_allowed_origins or settings.frontend_url,
            "auto_create_tables": settings.auto_create_tables,
            "trusted_proxy_ips": settings.api_rate_limit_trusted_proxy_ips,
            "rate_limit_backend": settings.api_rate_limit_backend,
            "redis_configured": bool(settings.redis_url),
            "auth_throttle_backend": settings.auth_throttle_backend,
            "api_key_profile_cache_ttl_seconds": settings.api_key_profile_cache_ttl_seconds,
            "request_logging_enabled": settings.request_logging_enabled,
            "request_id_header": settings.request_id_header,
            "metrics_enabled": settings.metrics_enabled,
            "security_headers_enabled": settings.security_headers_enabled,
            "content_security_policy": settings.content_security_policy,
        },
        "warnings": warnings,
    }
    if not is_ready:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=payload)  # type: ignore[return-value]
    return payload


@router.get("/metrics", summary="Metricas operativas basicas de la API")
def metrics(_current_user: User = Depends(require_metrics_viewer)) -> dict[str, object]:
    """Entrega contadores HTTP livianos para operacion inicial.

    No reemplaza Prometheus/OpenTelemetry, pero permite ver salud operacional
    durante demo, preproduccion y despliegues pequenos. Requiere usuario
    autenticado porque expone rutas, codigos HTTP y latencias.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "metrics_enabled": settings.metrics_enabled,
        "http": metrics_service.snapshot(),
        "bulk_jobs": metrics_service.bulk_snapshot(),
    }


@router.get("/metrics/prometheus", response_class=PlainTextResponse, summary="Metricas operativas en formato Prometheus")
def prometheus_metrics(_current_user: User = Depends(require_metrics_viewer)) -> PlainTextResponse:
    """Entrega metricas en texto plano compatible con Prometheus."""
    return PlainTextResponse(metrics_service.prometheus_text(), media_type="text/plain; version=0.0.4; charset=utf-8")
