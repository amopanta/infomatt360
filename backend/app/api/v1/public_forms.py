"""Formularios abiertos: captura publica por token/enlace, sin cuenta.

Endpoints administrativos (crear/listar/revocar enlaces) requieren sesion
y el permiso `builder.write`, igual que otras acciones de administracion
del constructor (`acta.py`, `xlsform.py`). Los dos endpoints de captura
(`GET /{token}`, `POST /{token}/submit`) son deliberadamente publicos --
el equivalente funcional de abrir un formulario de LimeSurvey por enlace
sin iniciar sesion -- protegidos por el token en si mismo mas throttling
por IP (mismo patron que `POST /enrollment/validate` y
`POST /emergency-access/redeem`).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BUILDER_WRITE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.schemas.builder_public_link import BuilderPublicLinkCreate, BuilderPublicLinkIssued, BuilderPublicLinkRead
from app.schemas.public_form import PublicFormSubmitRequest, PublicFormSubmitResponse
from app.schemas.runtime import RuntimeTemplate
from app.schemas.runtime_record import RuntimeRecordCreate
from app.services.auth_throttle_service import auth_throttle_service
from app.services.builder_public_link_service import builder_public_link_service
from app.services.runtime_record_service import runtime_record_service
from app.services.runtime_service import runtime_service

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/links", response_model=BuilderPublicLinkIssued, summary="Generar un enlace publico de captura para una plantilla publicada")
def create_public_link(payload: BuilderPublicLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderPublicLinkIssued:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == payload.template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    try:
        return builder_public_link_service.create_link(db, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/links/{template_id}", response_model=list[BuilderPublicLinkRead], summary="Listar enlaces publicos de una plantilla")
def list_public_links(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderPublicLinkRead]:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    require_project_permission(db, current_user.id, template.project_id, BUILDER_WRITE)
    return builder_public_link_service.list_links(db, template_id)


@router.post("/links/{link_id}/revoke", response_model=BuilderPublicLinkRead, summary="Revocar un enlace publico antes de su vencimiento")
def revoke_public_link(link_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderPublicLinkRead:
    link = builder_public_link_service.get_link(db, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enlace publico no encontrado")
    require_project_permission(db, current_user.id, link.project_id, BUILDER_WRITE)
    return builder_public_link_service.revoke_link(db, link_id)


@router.get("/{token}", response_model=RuntimeTemplate, summary="Cargar un formulario abierto por su enlace publico (sin sesion)")
def get_public_form(token: str, request: Request, db: Session = Depends(get_db)) -> RuntimeTemplate:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "public-form-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        link = builder_public_link_service.validate_token(db, token)
    except ValueError as exc:
        allowed = auth_throttle_service.record_attempt(db, "public-form-ip", ip_address, maximum=20, window_minutes=15, block_minutes=15)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    auth_throttle_service.clear(db, "public-form-ip", ip_address)
    return runtime_service.build_template_runtime(db, link.template_id)


@router.post("/{token}/submit", response_model=PublicFormSubmitResponse, summary="Enviar una respuesta a un formulario abierto (sin sesion)")
def submit_public_form(token: str, payload: PublicFormSubmitRequest, request: Request, db: Session = Depends(get_db)) -> PublicFormSubmitResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "public-form-submit-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        link = builder_public_link_service.validate_token(db, token)
    except ValueError as exc:
        allowed = auth_throttle_service.record_attempt(db, "public-form-submit-ip", ip_address, maximum=20, window_minutes=15, block_minutes=15)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    auth_throttle_service.clear(db, "public-form-submit-ip", ip_address)

    try:
        builder_public_link_service.reserve_submission_slot(db, link)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record_payload = RuntimeRecordCreate(
        project_id=link.project_id,
        template_id=link.template_id,
        status="submitted",
        device_id=payload.device_id,
        ip_address=ip_address,
        values=payload.values,
    )
    record = runtime_record_service.save_record(db, record_payload, user_id=None)
    return PublicFormSubmitResponse(submitted=True, record_id=record.id)
