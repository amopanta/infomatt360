from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.messages import InternalMessageCreate, InternalMessageRead, MailProfileCreate, MailProfileRead
from app.services.assignment_service import assignment_service
from app.services.message_service import message_service

router = APIRouter()


@router.post("/profiles", response_model=MailProfileRead)
def create_mail_profile(payload: MailProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MailProfileRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.create_mail_profile(db, payload)


@router.get("/profiles/{project_id}", response_model=list[MailProfileRead])
def list_mail_profiles(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[MailProfileRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_mail_profiles(db, project_id)


@router.post("/internal", response_model=InternalMessageRead)
def create_internal_message(payload: InternalMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> InternalMessageRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.create_message(db, payload, current_user.id)


@router.get("/internal/{project_id}", response_model=list[InternalMessageRead])
def list_internal_messages(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[InternalMessageRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_messages(db, project_id, current_user.id)
