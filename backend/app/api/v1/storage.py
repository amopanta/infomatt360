from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.storage import StorageProfileCreate, StorageProfileRead
from app.services.assignment_service import assignment_service
from app.services.storage_service import storage_service

router = APIRouter()


@router.post("/", response_model=StorageProfileRead)
def create_storage_profile(payload: StorageProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> StorageProfileRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return storage_service.create_profile(db, payload)


@router.get("/project/{project_id}", response_model=list[StorageProfileRead])
def list_storage_profiles(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[StorageProfileRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return storage_service.list_profiles(db, project_id)
