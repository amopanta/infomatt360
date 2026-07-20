from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.models.messages import MailProfile
from app.schemas.messages import (
    ExternalMailMessageRead,
    ExternalMailMessageUpdate,
    InternalMessageCreate,
    InternalMessageRead,
    InternalMessageUpdate,
    MailAutoconfigSuggestion,
    MailProfileCreate,
    MailProfileRead,
    MailTestSendResponse,
    MessageCounts,
)
from app.services.assignment_service import assignment_service
from app.services.mail_autoconfig_service import mail_autoconfig_service
from app.services.message_service import message_service

router = APIRouter()


@router.get("/profiles/autoconfig", response_model=MailAutoconfigSuggestion)
def suggest_mail_autoconfig(email: str, _current_user: User = Depends(get_current_user)) -> MailAutoconfigSuggestion:
    suggestion = mail_autoconfig_service.suggest_config(email)
    if suggestion is None:
        return MailAutoconfigSuggestion(found=False)
    return MailAutoconfigSuggestion(found=True, **suggestion)


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


@router.post("/profiles/{profile_id}/test-send", response_model=MailTestSendResponse)
def test_send_mail_profile(profile_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MailTestSendResponse:
    profile = db.query(MailProfile).filter(MailProfile.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de correo no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, profile.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    sent, detail = mail_autoconfig_service.send_test_email(profile)
    return MailTestSendResponse(sent=sent, detail=detail)


@router.post("/internal", response_model=InternalMessageRead)
def create_internal_message(payload: InternalMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> InternalMessageRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    if not message_service.user_exists_in_project(db, payload.recipient_id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El destinatario no pertenece al proyecto")
    return message_service.create_message(db, payload, current_user.id)


@router.get("/internal/{project_id}/inbox", response_model=list[InternalMessageRead])
def list_internal_inbox(project_id: str, status_filter: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[InternalMessageRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_inbox(db, project_id, current_user.id, status_filter, min(limit, 100), max(offset, 0))


@router.get("/internal/{project_id}/sent", response_model=list[InternalMessageRead])
def list_internal_sent(project_id: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[InternalMessageRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_sent(db, project_id, current_user.id, min(limit, 100), max(offset, 0))


@router.get("/internal/{project_id}/counts", response_model=MessageCounts)
def message_counts(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MessageCounts:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.counts(db, project_id, current_user.id)


@router.get("/internal/{project_id}", response_model=list[InternalMessageRead])
def list_internal_messages(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[InternalMessageRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_inbox(db, project_id, current_user.id)


@router.patch("/internal/{project_id}/{message_id}", response_model=InternalMessageRead)
def update_internal_message(project_id: str, message_id: str, payload: InternalMessageUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> InternalMessageRead:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    message = message_service.get_project_message_for_user(db, message_id, project_id, current_user.id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mensaje no encontrado")
    return message_service.set_status(db, message, payload.status)


@router.get("/external/{project_id}/inbox", response_model=list[ExternalMailMessageRead])
def list_external_inbox(
    project_id: str,
    mail_profile_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExternalMailMessageRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return message_service.list_external_inbox(db, project_id, mail_profile_id, status_filter, min(limit, 100), max(offset, 0))


@router.patch("/external/{project_id}/{message_id}", response_model=ExternalMailMessageRead)
def update_external_message(project_id: str, message_id: str, payload: ExternalMailMessageUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ExternalMailMessageRead:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    message = message_service.get_project_external_message(db, message_id, project_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mensaje no encontrado")
    return message_service.set_external_status(db, message, payload.status)
