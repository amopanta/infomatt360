from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.emergency_access import EmergencyAccessKey
from app.models.identity import User
from app.schemas.emergency_access import (
    EmergencyAccessKeyCreate,
    EmergencyAccessKeyIssued,
    EmergencyAccessKeyRead,
    EmergencyAccessRedeemRequest,
    EmergencyAccessRedeemResponse,
)
from app.services.auth_throttle_service import auth_throttle_service
from app.services.emergency_access_service import emergency_access_service

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/keys", response_model=EmergencyAccessKeyIssued, summary="Emitir credencial de emergencia time-boxed")
def issue_key(payload: EmergencyAccessKeyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EmergencyAccessKeyIssued:
    require_project_permission(db, current_user.id, payload.project_id, IDENTITY_USERS_MANAGE)
    return emergency_access_service.issue(db, payload, current_user.id)


@router.get("/keys/project/{project_id}", response_model=list[EmergencyAccessKeyRead], summary="Listar credenciales de emergencia de un proyecto")
def list_keys(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[EmergencyAccessKeyRead]:
    require_project_permission(db, current_user.id, project_id, IDENTITY_USERS_MANAGE)
    return emergency_access_service.list_keys(db, project_id)


@router.post("/keys/{key_id}/revoke", response_model=EmergencyAccessKeyRead, summary="Revocar una credencial de emergencia antes de su vencimiento")
def revoke_key(key_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> EmergencyAccessKeyRead:
    require_project_permission(db, current_user.id, _project_of(db, key_id), IDENTITY_USERS_MANAGE)
    return emergency_access_service.revoke(db, key_id)


def _project_of(db: Session, key_id: str) -> str:
    row = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.id == key_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Llave de emergencia no encontrada")
    return row.project_id


@router.post("/redeem", response_model=EmergencyAccessRedeemResponse, summary="Canjear una credencial de emergencia por una sesion")
def redeem_key(payload: EmergencyAccessRedeemRequest, request: Request, db: Session = Depends(get_db)) -> EmergencyAccessRedeemResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "emergency-redeem-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        result = emergency_access_service.redeem(db, payload.code)
    except HTTPException as exc:
        allowed = auth_throttle_service.record_attempt(db, "emergency-redeem-ip", ip_address, maximum=10, window_minutes=15, block_minutes=15)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise
    auth_throttle_service.clear(db, "emergency-redeem-ip", ip_address)
    return result
