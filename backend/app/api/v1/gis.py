from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import allowed_participant_ids
from app.db.session import get_db
from app.models.identity import User
from app.models.gis import GisFeature
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.schemas.gis import GisFeatureCreate, GisFeatureRead, GisLayerCreate, GisLayerRead, GisMapFeature, GisProjectMap
from app.services.assignment_service import assignment_service
from app.services.gis_service import gis_service

router = APIRouter()


def _visible_feature(db: Session, feature: GisFeatureCreate | GisFeatureRead | GisMapFeature, allowed: set[str]) -> bool:
    participant_id = getattr(feature, "participant_id", None)
    if participant_id:
        participant = db.get(Participant, participant_id)
        return bool(participant and participant.project_id == feature.project_id and participant_id in allowed)
    if feature.record_id:
        record = db.get(RuntimeRecord, feature.record_id)
        return bool(record and record.project_id == feature.project_id and record.participant_id in allowed)
    if isinstance(feature, GisMapFeature) and feature.source == "gis":
        row = db.get(GisFeature, feature.id)
        return bool(row and row.project_id == feature.project_id and row.participant_id in allowed)
    return False


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
    allowed = allowed_participant_ids(db, current_user.id, payload.project_id)
    if allowed is not None and not _visible_feature(db, payload, set(allowed)):
        raise HTTPException(status_code=403, detail="Elemento fuera del territorio asignado")
    return gis_service.create_feature(db, payload)


@router.get("/features/{project_id}", response_model=list[GisFeatureRead])
def list_features(project_id: str, layer_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[GisFeatureRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    features = gis_service.list_features(db, project_id, layer_id)
    allowed = allowed_participant_ids(db, current_user.id, project_id)
    if allowed is None:
        return features
    allowed_set = set(allowed)
    return [item for item in features if _visible_feature(db, item, allowed_set)]


@router.get("/map/{project_id}", response_model=GisProjectMap)
def project_map(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> GisProjectMap:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    result = gis_service.project_map(db, project_id)
    allowed = allowed_participant_ids(db, current_user.id, project_id)
    if allowed is not None:
        allowed_set = set(allowed)
        result.features = [item for item in result.features if _visible_feature(db, item, allowed_set)]
    return result


@router.get("/features/{project_id}/nearby", response_model=list[GisMapFeature])
def nearby_features(project_id: str, lat: float, lng: float, radius_km: float = 1.0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[GisMapFeature]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    features = gis_service.nearby_features(db, project_id, lat, lng, radius_km)
    allowed = allowed_participant_ids(db, current_user.id, project_id)
    if allowed is None:
        return features
    allowed_set = set(allowed)
    return [item for item in features if _visible_feature(db, item, allowed_set)]
