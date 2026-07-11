from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.files import FileAssetCreate, FileAssetRead
from app.services.assignment_service import assignment_service
from app.services.file_service import file_service

router = APIRouter()
UPLOAD_ASSET_TYPES = {"FILE", "PDF", "MULTIFILE", "IMAGE", "AUDIO", "VIDEO", "SIGNATURE"}


def validate_asset_relations(db: Session, project_id: str, participant_id: str | None, record_id: str | None) -> None:
    if participant_id and not db.query(Participant).filter(Participant.id == participant_id, Participant.project_id == project_id).first():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El participante no pertenece al proyecto")
    if record_id and not db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id, RuntimeRecord.project_id == project_id).first():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El registro no pertenece al proyecto")


@router.post("/", response_model=FileAssetRead)
def create_file_asset(payload: FileAssetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileAssetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    validate_asset_relations(db, payload.project_id, payload.participant_id, payload.record_id)
    return file_service.create_asset(db, payload, current_user.id)


@router.post("/upload", response_model=FileAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_file_asset(
    project_id: str = Form(...),
    asset_type: str = Form(...),
    participant_id: str | None = Form(None),
    record_id: str | None = Form(None),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileAssetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    if asset_type.upper() not in UPLOAD_ASSET_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tipo de evidencia no soportado")
    validate_asset_relations(db, project_id, participant_id, record_id)
    try:
        return await file_service.upload(
            db,
            project_id=project_id,
            asset_type=asset_type,
            upload=upload,
            user_id=current_user.id,
            participant_id=participant_id,
            record_id=record_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc


@router.get("/project/{project_id}", response_model=list[FileAssetRead])
def list_project_files(project_id: str, participant_id: str | None = None, record_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FileAssetRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return file_service.list_assets(db, project_id, participant_id, record_id)
