"""Asignaciones de departamento/municipio a usuarios del proyecto."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import IDENTITY_USERS_MANAGE
from app.db.session import get_db
from app.models.case_management import UserTerritory
from app.models.identity import User
from app.schemas.case_management import TerritoryCreate, TerritoryRead
from app.services.assignment_service import assignment_service

router = APIRouter()


@router.get("/{project_id}", response_model=list[TerritoryRead])
def list_territories(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    return db.query(UserTerritory).filter(UserTerritory.project_id == project_id).order_by(UserTerritory.department, UserTerritory.municipality).all()


@router.post("/{project_id}", response_model=TerritoryRead)
def assign_territory(project_id: str, payload: TerritoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    if not db.get(User, payload.user_id) or not assignment_service.user_has_project_access(db, payload.user_id, project_id):
        raise HTTPException(status_code=422, detail="El usuario debe tener acceso al proyecto")
    row = UserTerritory(project_id=project_id, user_id=payload.user_id, department=payload.department.strip(), municipality=payload.municipality.strip())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El territorio ya está asignado")
    db.refresh(row)
    return row


@router.delete("/{project_id}/{territory_id}", status_code=204)
def remove_territory(project_id: str, territory_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_project_permission(db, user.id, project_id, IDENTITY_USERS_MANAGE)
    row = db.query(UserTerritory).filter(UserTerritory.id == territory_id, UserTerritory.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Territorio no encontrado")
    db.delete(row)
    db.commit()
