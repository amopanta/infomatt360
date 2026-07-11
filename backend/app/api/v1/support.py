from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_project_permission
from app.core.permissions import RECORDS_WRITE, SUPPORT_TICKETS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.models.support import SupportTicket
from app.schemas.support import SupportTicketCreate, SupportTicketRead, SupportTicketResolve
from app.services.assignment_service import assignment_service
from app.services.support_service import support_service

router = APIRouter()


@router.post("/tickets", response_model=SupportTicketRead, summary="Reportar una falla tecnica desde la tablet")
def create_ticket(payload: SupportTicketCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SupportTicketRead:
    require_any_project_permission(db, current_user.id, payload.project_id, {RECORDS_WRITE, SUPPORT_TICKETS_MANAGE})
    return support_service.create_ticket(db, payload, current_user.id)


@router.get("/tickets/project/{project_id}", response_model=list[SupportTicketRead], summary="Listar tickets de soporte de un proyecto")
def list_tickets(project_id: str, status_filter: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[SupportTicketRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return support_service.list_tickets(db, project_id, status_filter)


@router.post("/tickets/{ticket_id}/resolve", response_model=SupportTicketRead, summary="Marcar un ticket como resuelto por soporte humano")
def resolve_ticket(ticket_id: str, _payload: SupportTicketResolve, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SupportTicketRead:
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    require_any_project_permission(db, current_user.id, ticket.project_id, {SUPPORT_TICKETS_MANAGE})
    return support_service.resolve_ticket(db, ticket_id, current_user.id)
