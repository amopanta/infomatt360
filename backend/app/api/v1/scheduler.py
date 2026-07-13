from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import BACKUPS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.scheduler import ScheduledTaskCreate, ScheduledTaskRead, TaskRunCreate, TaskRunRead
from app.services.assignment_service import assignment_service
from app.services.scheduler_service import scheduler_service

router = APIRouter()

# Permiso especifico exigido por task_type, ademas del acceso general al
# proyecto. Hoy solo "backup" tiene un permiso dedicado (BACKUPS_MANAGE,
# el mismo que exige el boton manual en backups.py); un task_type nuevo sin
# entrada aqui sigue protegido solo por pertenencia al proyecto.
TASK_TYPE_PERMISSIONS = {"backup": BACKUPS_MANAGE}


@router.post("/tasks", response_model=ScheduledTaskRead)
def create_task(payload: ScheduledTaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ScheduledTaskRead:
    required_permission = TASK_TYPE_PERMISSIONS.get(payload.task_type)
    if required_permission:
        require_project_permission(db, current_user.id, payload.project_id, required_permission)
    elif not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return scheduler_service.create_task(db, payload)


@router.get("/tasks/{project_id}", response_model=list[ScheduledTaskRead])
def list_tasks(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ScheduledTaskRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return scheduler_service.list_tasks(db, project_id)


@router.post("/runs", response_model=TaskRunRead)
def create_run(payload: TaskRunCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> TaskRunRead:
    return scheduler_service.create_run(db, payload)


@router.get("/runs/{task_id}", response_model=list[TaskRunRead])
def list_runs(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[TaskRunRead]:
    return scheduler_service.list_runs(db, task_id)
