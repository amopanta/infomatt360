"""Bloquea la API operativa hasta completar el instalador de primer arranque.

Inerte por defecto: solo actua cuando `settings.installer_enforced` esta
activo. Asi no afecta despliegues, la demo ni las pruebas existentes que
nunca pasan por el instalador.
"""

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.installation import InstallationState

ALLOWED_PATH_PREFIXES = ("/api/v1/install", "/api/v1/public", "/health", "/docs", "/redoc", "/openapi.json")


class InstallGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if not settings.installer_enforced:
            return await call_next(request)
        if request.url.path.startswith(ALLOWED_PATH_PREFIXES):
            return await call_next(request)

        db = SessionLocal()
        try:
            row = db.query(InstallationState).first()
            installed = bool(row and row.is_installed)
        finally:
            db.close()

        if not installed:
            return JSONResponse(status_code=503, content={"code": "NOT_INSTALLED", "detail": "El sistema requiere completar el instalador de primer arranque"})
        return await call_next(request)
