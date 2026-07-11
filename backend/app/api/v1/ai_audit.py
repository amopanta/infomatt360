from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import AI_AUDIT_MANAGE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.models.runtime_record import RuntimeRecord
from app.schemas.ai import AiAuditConfigCreate, AiAuditConfigRead, AiCheckRead
from app.services.ai_audit_service import ai_audit_service
from app.services.assignment_service import assignment_service

router = APIRouter()


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
