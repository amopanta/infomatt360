from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.forms import FormCreate, FormRead
from app.services.assignment_service import assignment_service
from app.services.form_service import form_service

router = APIRouter()


@router.post("/", response_model=FormRead, summary="Crear formulario dinamico")
def create_form(payload: FormCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FormRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return form_service.create_form(db, payload)


@router.get("/project/{project_id}", response_model=list[FormRead], summary="Listar formularios por proyecto")
def list_project_forms(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FormRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return form_service.list_forms(db, project_id)
