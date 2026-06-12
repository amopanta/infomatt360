from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.records import RecordCreate, RecordEventRead, RecordRead
from app.services.assignment_service import assignment_service
from app.services.record_service import record_service

router = APIRouter()


@router.post("/", response_model=RecordRead, summary="Crear registro o respuesta")
def create_record(payload: RecordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> RecordRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return record_service.create_record(db, payload, current_user.id)


@router.get("/project/{project_id}", response_model=list[RecordRead], summary="Listar registros por proyecto")
def list_project_records(
    project_id: str,
    participant_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecordRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return record_service.list_records(db, project_id, participant_id)


@router.get("/{record_id}/events", response_model=list[RecordEventRead], summary="Historial del registro")
def list_record_events(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RecordEventRead]:
    return record_service.list_record_events(db, record_id)
