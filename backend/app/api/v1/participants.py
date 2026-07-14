from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.participants import ParticipantCreate, ParticipantHistoryItem, ParticipantRead
from app.services.assignment_service import assignment_service
from app.services.participant_service import participant_service

router = APIRouter()


@router.post("/", response_model=ParticipantRead, summary="Crear participante")
def create_participant(payload: ParticipantCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return participant_service.create_participant(db, payload)


@router.get("/project/{project_id}", response_model=list[ParticipantRead], summary="Listar participantes por proyecto")
def list_project_participants(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return participant_service.list_participants(db, project_id)


def _require_participant(db: Session, current_user: User, participant_id: str) -> ParticipantRead:
    """Resuelve un participante validando acceso al proyecto sin filtrar por
    project_id en la consulta (evita revelar si el id existe en otro
    proyecto vs. si simplemente no existe -- ambos casos dan 404)."""
    participant = participant_service.get_participant(db, participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante no encontrado")
    if not assignment_service.user_has_project_access(db, current_user.id, participant.project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participante no encontrado")
    return participant


@router.get("/{participant_id}", response_model=ParticipantRead, summary="Consultar un participante")
def get_participant(participant_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ParticipantRead:
    return _require_participant(db, current_user, participant_id)


@router.get("/{participant_id}/history", response_model=list[ParticipantHistoryItem], summary="Historial unificado del participante entre plantillas y canales")
def get_participant_history(participant_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ParticipantHistoryItem]:
    _require_participant(db, current_user, participant_id)
    return participant_service.get_participant_history(db, participant_id)
