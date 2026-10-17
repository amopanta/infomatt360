from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission, require_project_permission
from app.core.permissions import AI_AUDIT_MANAGE, BUILDER_WRITE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.models.runtime_record import RuntimeRecord
from app.schemas.ai import AiAuditConfigCreate, AiAuditConfigRead, AiCheckRead
from app.services.ai_audit_service import ai_audit_service
from app.services.ai_provider_service import connection_for, get_provider, list_providers, provider_to_read, save_provider
from app.services.assignment_service import assignment_service

router = APIRouter()


class AiProviderInput(BaseModel):
    project_id: str
    name: str
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    status: str = "active"


@router.get("/providers/{project_id}")
def provider_list(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict]:
    require_any_project_permission(db, current_user.id, project_id, {AI_AUDIT_MANAGE, BUILDER_WRITE})
    return [provider_to_read(row) for row in list_providers(db, project_id)]


@router.post("/providers")
def provider_create(payload: AiProviderInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    require_project_permission(db, current_user.id, payload.project_id, AI_AUDIT_MANAGE)
    try:
        row = save_provider(db, project_id=payload.project_id, name=payload.name,
                            kind=payload.provider, model=payload.model, base_url=payload.base_url,
                            api_key=payload.api_key, status=payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return provider_to_read(row)


@router.put("/providers/{provider_id}")
def provider_update(provider_id: str, payload: AiProviderInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    require_project_permission(db, current_user.id, payload.project_id, AI_AUDIT_MANAGE)
    row = get_provider(db, payload.project_id, provider_id)
    if not row:
        raise HTTPException(status_code=404, detail="Conexión de IA no encontrada")
    try:
        row = save_provider(db, project_id=payload.project_id, name=payload.name,
                            kind=payload.provider, model=payload.model, base_url=payload.base_url,
                            api_key=payload.api_key, status=payload.status, row=row)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return provider_to_read(row)


@router.post("/providers/{provider_id}/test")
def provider_test(provider_id: str, project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    require_project_permission(db, current_user.id, project_id, AI_AUDIT_MANAGE)
    row = get_provider(db, project_id, provider_id)
    if not row or row.status != "active":
        raise HTTPException(status_code=404, detail="Conexión activa no encontrada")
    try:
        connection = connection_for(row)
        ai_audit_service._call_llm("Responde únicamente con la palabra OK.", **vars(connection))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No se pudo conectar con el proveedor. Comprueba clave, modelo y cuota") from exc
    return {"connected": True}


def _template_project_id(db: Session, template_id: str) -> str:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    return template.project_id


@router.post("/config", response_model=AiAuditConfigRead, summary="Vincular una plantilla a la auditoria semantica con IA")
def create_config(payload: AiAuditConfigCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AiAuditConfigRead:
    project_id = _template_project_id(db, payload.template_id)
    require_project_permission(db, current_user.id, project_id, AI_AUDIT_MANAGE)
    return ai_audit_service.create_config(db, payload)


@router.get("/config/{template_id}", response_model=AiAuditConfigRead | None, summary="Consultar configuracion de auditoria de una plantilla")
def get_config(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AiAuditConfigRead | None:
    project_id = _template_project_id(db, template_id)
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return ai_audit_service.get_config(db, template_id)


@router.post("/records/{record_id}/analyze", response_model=AiCheckRead | None, summary="Reanalizar manualmente un registro ya guardado")
def analyze_record(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> AiCheckRead | None:
    record = db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    require_project_permission(db, current_user.id, record.project_id, AI_AUDIT_MANAGE)
    return ai_audit_service.audit_record(db, record)
