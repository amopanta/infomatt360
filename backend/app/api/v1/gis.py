from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.gis import GisFeatureCreate, GisFeatureRead, GisLayerCreate, GisLayerRead
from app.services.assignment_service import assignment_service
from app.services.gis_service import gis_service

router = APIRouter()


@router.post("/layers", response_model=GisLayerRead)
def create_layer(payload: GisLayerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> GisLayerRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return gis_service.create_layer(db, payload)


@router.get("/layers/{project_id}", response_model=list[GisLayerRead])
def list_layers(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[GisLayerRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return gis_service.list_layers(db, project_id)


@router.post("/features", response_model=GisFeatureRead)
def create_feature(payload: GisFeatureCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> GisFeatureRead:
    if not assignment_service.user_has_project_access(db, current_user.id, payload.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return gis_service.create_feature(db, payload)


@router.get("/features/{project_id}", response_model=list[GisFeatureRead])
def list_features(project_id: str, layer_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[GisFeatureRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return gis_service.list_features(db, project_id, layer_id)
