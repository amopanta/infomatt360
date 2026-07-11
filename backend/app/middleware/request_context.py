from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.services.metrics_service import metrics_service

logger = logging.getLogger("infomatt360.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Agrega request ID y log estructurado por solicitud HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        request_id = self._request_id(request)
        request.state.request_id = request_id
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if settings.metrics_enabled:
                metrics_service.record_http_request(request.url.path, status_code, duration_ms)
            try:
                response.headers[settings.request_id_header] = request_id
            except UnboundLocalError:
                pass
            if settings.request_logging_enabled:
                logger.info(
                    json.dumps(
                        {
                            "event": "http_request",
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                            "client_ip": request.client.host if request.client else "unknown",
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )

    def _request_id(self, request: Request) -> str:
        incoming = request.headers.get(settings.request_id_header)
        if incoming:
            clean = incoming.strip()
            if 1 <= len(clean) <= 80 and all(character.isalnum() or character in "-_." for character in clean):
                return clean
        return str(uuid4())
