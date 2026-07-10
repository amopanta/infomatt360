"""Cabeceras HTTP defensivas para respuestas del backend."""

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras de seguridad sin dificultar el consumo normal del API.

    La politica CSP se omite en Swagger/ReDoc para evitar romper recursos
    inline propios de la documentacion interactiva de FastAPI.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)
        if not settings.security_headers_enabled:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", settings.x_frame_options)
        response.headers.setdefault("Referrer-Policy", settings.referrer_policy)
        response.headers.setdefault("Permissions-Policy", settings.permissions_policy)

        if request.url.path not in DOCS_PATHS and settings.content_security_policy:
            response.headers.setdefault("Content-Security-Policy", settings.content_security_policy)

        return response
