"""Entrada principal del backend de InfoMatt360.

Este archivo crea la instancia FastAPI y registra las rutas base.
La logica de negocio no debe concentrarse aqui; cada modulo debe vivir en
su paquete correspondiente para mantener el sistema mantenible.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.db.init_db import init_db
from app.middleware.install_guard import InstallGuardMiddleware
from app.middleware.rate_limit import ApiRateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


def _upload_directory_failure() -> str | None:
    upload_path = Path(settings.upload_directory)
    if not upload_path.exists():
        return "UPLOAD_DIRECTORY debe existir en produccion"
    if not upload_path.is_dir():
        return "UPLOAD_DIRECTORY debe ser un directorio en produccion"
    probe = upload_path / ".infomatt360-startup-check"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return f"UPLOAD_DIRECTORY debe permitir escritura en produccion: {exc}"
    return None


def validate_startup_settings() -> None:
    """Bloquea configuraciones peligrosas cuando el ambiente es produccion."""
    if settings.environment.lower() not in {"production", "prod"}:
        return
    failures: list[str] = []
    if settings.debug:
        failures.append("DEBUG debe ser false en produccion")
    if settings.secret_key == "CHANGE_ME_IN_PRODUCTION" or settings.secret_key.startswith("change-this") or len(settings.secret_key) < 32:
        failures.append("SECRET_KEY debe ser fuerte y no usar el valor por defecto")
    if settings.auto_create_tables:
        failures.append("AUTO_CREATE_TABLES debe ser false en produccion")
    if settings.database_url.startswith("sqlite"):
        failures.append("DATABASE_URL no debe usar SQLite en produccion")
    if not settings.cors_allowed_origins or "*" in settings.cors_allowed_origins:
        failures.append("CORS_ALLOWED_ORIGINS debe ser explicito y no usar comodin")
    if not settings.frontend_url.startswith("https://"):
        failures.append("FRONTEND_URL debe usar HTTPS en produccion")
    cors_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    if any(not origin.startswith("https://") for origin in cors_origins):
        failures.append("Todos los origenes CORS deben usar HTTPS en produccion")
    if not settings.refresh_cookie_secure:
        failures.append("REFRESH_COOKIE_SECURE debe ser true en produccion")
    if settings.refresh_cookie_samesite.lower().strip() not in {"strict", "lax"}:
        failures.append("REFRESH_COOKIE_SAMESITE debe ser strict o lax en produccion")
    if not settings.api_rate_limit_enabled:
        failures.append("API_RATE_LIMIT_ENABLED debe ser true en produccion")
    if settings.api_rate_limit_backend.lower().strip() not in {"memory", "redis"}:
        failures.append("API_RATE_LIMIT_BACKEND debe ser memory o redis")
    if settings.auth_throttle_backend.lower().strip() not in {"db", "redis"}:
        failures.append("AUTH_THROTTLE_BACKEND debe ser db o redis")
    if (settings.api_rate_limit_backend.lower().strip() == "redis" or settings.auth_throttle_backend.lower().strip() == "redis") and not settings.redis_url:
        failures.append("REDIS_URL es obligatorio cuando rate limiting o auth throttling usan redis")
    if not settings.request_logging_enabled:
        failures.append("REQUEST_LOGGING_ENABLED debe ser true en produccion")
    if not settings.metrics_enabled:
        failures.append("METRICS_ENABLED debe ser true en produccion")
    if not settings.security_headers_enabled:
        failures.append("SECURITY_HEADERS_ENABLED debe ser true en produccion")
    upload_failure = _upload_directory_failure()
    if upload_failure:
        failures.append(upload_failure)
    if failures:
        raise RuntimeError("Configuracion insegura para produccion: " + "; ".join(failures))


def create_app() -> FastAPI:
    """Construye y configura la aplicacion FastAPI.

    Se usa una funcion fabrica para facilitar pruebas, configuracion por
    ambiente y futuros despliegues multiworker.
    """
    validate_startup_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """Inicializa tablas de desarrollo durante el ciclo de vida moderno."""
        if settings.auto_create_tables:
            init_db()
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Core API para InfoMatt360",
        lifespan=lifespan,
    )
    allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    if not allowed_origins and settings.frontend_url:
        allowed_origins = [settings.frontend_url]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", settings.request_id_header],
        expose_headers=[settings.request_id_header],
    )
    app.add_middleware(ApiRateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(InstallGuardMiddleware)

    # Ruta simple para balanceadores, monitoreo y pruebas iniciales.
    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    # Todas las rutas versionadas viven bajo /api/v1.
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
