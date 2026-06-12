from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.files import FileAssetCreate, FileAssetRead
from app.services.assignment_service import assignment_service
from app.services.file_service import file_service

router = APIRouter()


@router.post("/", response_model=FileAssetRead)
def create_file_asset(payload: FileAssetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FileAssetRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return file_service.create_asset(db, payload, current_user.id)


@router.get("/project/{project_id}", response_model=list[FileAssetRead])
def list_project_files(project_id: str, participant_id: str | None = None, record_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FileAssetRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return file_service.list_assets(db, project_id, participant_id, record_id)
