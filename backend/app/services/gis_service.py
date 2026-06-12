from sqlalchemy.orm import Session

from app.models.gis import GisFeature, GisLayer
from app.schemas.gis import GisFeatureCreate, GisFeatureRead, GisLayerCreate, GisLayerRead


def layer_to_read(row: GisLayer) -> GisLayerRead:
    return GisLayerRead(id=row.id, project_id=row.project_id, name=row.name, layer_type=row.layer_type, style_json=row.style_json, status=row.status)


def feature_to_read(row: GisFeature) -> GisFeatureRead:
    return GisFeatureRead(
        id=row.id,
        project_id=row.project_id,
        layer_id=row.layer_id,
        participant_id=row.participant_id,
        record_id=row.record_id,
        feature_type=row.feature_type,
        latitude=row.latitude,
        longitude=row.longitude,
        geometry_json=row.geometry_json,
        properties_json=row.properties_json,
        status=row.status,
    )


class GisService:
    def create_layer(self, db: Session, payload: GisLayerCreate) -> GisLayerRead:
        row = GisLayer(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return layer_to_read(row)

    def list_layers(self, db: Session, project_id: str) -> list[GisLayerRead]:
        rows = db.query(GisLayer).filter(GisLayer.project_id == project_id).order_by(GisLayer.created_at.desc()).all()
        return [layer_to_read(row) for row in rows]

    def create_feature(self, db: Session, payload: GisFeatureCreate) -> GisFeatureRead:
        row = GisFeature(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return feature_to_read(row)

    def list_features(self, db: Session, project_id: str, layer_id: str | None = None) -> list[GisFeatureRead]:
        query = db.query(GisFeature).filter(GisFeature.project_id == project_id)
        if layer_id:
            query = query.filter(GisFeature.layer_id == layer_id)
        rows = query.order_by(GisFeature.created_at.desc()).all()
        return [feature_to_read(row) for row in rows]


gis_service = GisService()
