from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BACKUPS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.backup import BackupJobRead
from app.services.backup_service import backup_service

router = APIRouter()


@router.post("/run", response_model=BackupJobRead, summary="Ejecutar respaldo de base de datos")
def run_backup(project_id: str, storage_profile_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BackupJobRead:
    require_project_permission(db, current_user.id, project_id, BACKUPS_MANAGE)
    return backup_service.run_backup(db, project_id, current_user.id, storage_profile_id)


@router.get("/project/{project_id}", response_model=list[BackupJobRead], summary="Listar historial de respaldos")
def list_backups(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BackupJobRead]:
    require_project_permission(db, current_user.id, project_id, BACKUPS_MANAGE)
    return backup_service.list_backups(db, project_id)
