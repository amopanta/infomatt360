from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission
from app.core.permissions import MESSAGES_READ, RECORDS_APPROVE, RECORDS_REVIEW
from app.db.session import get_db
from app.models.identity import User
from app.schemas.whatsapp import WhatsAppNotificationRead
from app.services.whatsapp_service import whatsapp_service

router = APIRouter()


@router.get("/notifications/project/{project_id}", response_model=list[WhatsAppNotificationRead], summary="Historial de notificaciones WhatsApp de un proyecto")
def list_whatsapp_notifications(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[WhatsAppNotificationRead]:
    require_any_project_permission(db, current_user.id, project_id, {MESSAGES_READ, RECORDS_REVIEW, RECORDS_APPROVE})
    return whatsapp_service.list_notifications(db, project_id)
