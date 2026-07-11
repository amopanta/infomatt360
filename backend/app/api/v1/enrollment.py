from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.enrollment import QrGenerateRequest, QrValidateRequest, QrValidateResponse
from app.services.assignment_service import assignment_service
from app.services.auth_throttle_service import auth_throttle_service
from app.services.enrollment_service import enrollment_service

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/qr", summary="Generar codigo QR de enrolamiento para un gestor")
def generate_qr(payload: QrGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    require_project_permission(db, current_user.id, payload.project_id, IDENTITY_USERS_MANAGE)
    if not assignment_service.user_has_project_access(db, payload.user_id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El gestor no tiene acceso a ese proyecto")
    png_bytes, raw_token = enrollment_service.generate_qr_png(db, payload)
    return Response(content=png_bytes, media_type="image/png", headers={"X-Enrollment-Token": raw_token})


@router.post("/validate", response_model=QrValidateResponse, summary="Validar codigo QR de enrolamiento")
def validate_qr(payload: QrValidateRequest, request: Request, db: Session = Depends(get_db)) -> QrValidateResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "qr-validate-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        result = enrollment_service.validate(db, payload)
    except HTTPException as exc:
        allowed = auth_throttle_service.record_attempt(db, "qr-validate-ip", ip_address, maximum=10, window_minutes=15, block_minutes=15)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise
    auth_throttle_service.clear(db, "qr-validate-ip", ip_address)
    return result
