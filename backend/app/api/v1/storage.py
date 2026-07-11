from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.storage import StorageProfileCreate, StorageProfileRead
from app.services.assignment_service import assignment_service
from app.services.gdrive_storage_service import gdrive_storage_service
from app.services.storage_service import storage_service

router = APIRouter()


@router.get("/oauth/gdrive/authorize", summary="Iniciar autorizacion de Google Drive para un proyecto")
def authorize_gdrive(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return {"authorization_url": gdrive_storage_service.build_authorization_url(project_id)}


@router.get("/oauth/gdrive/callback", response_model=StorageProfileRead, summary="Callback de OAuth de Google Drive")
def gdrive_oauth_callback(code: str, state: str, db: Session = Depends(get_db)) -> StorageProfileRead:
    project_id = gdrive_storage_service.verify_state(state)
    tokens = gdrive_storage_service.exchange_code_for_tokens(code)
    return gdrive_storage_service.connect_profile(db, project_id, tokens)


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
