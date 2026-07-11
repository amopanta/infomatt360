import json

from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.gis import GisFeature, GisLayer
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.gis import GisFeatureCreate, GisFeatureRead, GisLayerCreate, GisLayerRead, GisMapFeature, GisProjectMap


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

    def project_map(self, db: Session, project_id: str) -> GisProjectMap:
        """Construye la vista de mapa del proyecto desde capas GIS y registros Runtime."""
        features = self._manual_map_features(db, project_id) + self._runtime_map_features(db, project_id)
        features.sort(key=lambda item: (item.template_name or "", item.label))
        return GisProjectMap(project_id=project_id, features=features)

    def _manual_map_features(self, db: Session, project_id: str) -> list[GisMapFeature]:
        rows = db.query(GisFeature).filter(GisFeature.project_id == project_id, GisFeature.status == "active").order_by(GisFeature.created_at.desc()).all()
        features: list[GisMapFeature] = []
        for row in rows:
            point = self._point_from_feature(row.latitude, row.longitude, row.geometry_json)
            if point is None:
                continue
            longitude, latitude = point
            features.append(
                GisMapFeature(
                    id=row.id,
                    project_id=row.project_id,
                    source="gis",
                    feature_type=row.feature_type,
                    latitude=latitude,
                    longitude=longitude,
                    label=f"Elemento GIS {row.feature_type}",
                    record_id=row.record_id,
                    geometry_json=row.geometry_json,
                    properties_json=row.properties_json,
                )
            )
        return features

    def _runtime_map_features(self, db: Session, project_id: str) -> list[GisMapFeature]:
        rows = (
            db.query(RuntimeRecordValue, RuntimeRecord, BuilderTemplate.name)
            .join(RuntimeRecord, RuntimeRecord.id == RuntimeRecordValue.record_id)
            .join(BuilderTemplate, BuilderTemplate.id == RuntimeRecord.template_id)
            .filter(RuntimeRecord.project_id == project_id)
            .order_by(RuntimeRecord.created_at.desc())
            .all()
        )
        features: list[GisMapFeature] = []
        for value, record, template_name in rows:
            geometry = self._geometry_from_json(value.field_value_json)
            if geometry is None:
                continue
            point = self._representative_point(geometry)
            if point is None:
                continue
            longitude, latitude = point
            features.append(
                GisMapFeature(
                    id=value.id,
                    project_id=record.project_id,
                    source="runtime",
                    feature_type=geometry["type"],
                    latitude=latitude,
                    longitude=longitude,
                    label=value.field_name,
                    template_id=record.template_id,
                    template_name=template_name,
                    record_id=record.id,
                    field_name=value.field_name,
                    geometry_json=json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
                )
            )
        return features

    def _point_from_feature(self, latitude: str | None, longitude: str | None, geometry_json: str | None) -> tuple[float, float] | None:
        if latitude is not None and longitude is not None:
            try:
                point = (float(longitude), float(latitude))
            except ValueError:
                point = None
            if point and self._valid_coordinate(point):
                return point
        return self._representative_point(self._geometry_from_json(geometry_json))

    def _geometry_from_json(self, raw: str | None) -> dict | None:
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        if isinstance(value, dict) and value.get("type") in {"Point", "LineString", "Polygon"}:
            return value
        if isinstance(value, dict):
            latitude = value.get("lat", value.get("latitude"))
            longitude = value.get("lng", value.get("lon", value.get("longitude")))
            if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
                point = (float(longitude), float(latitude))
                if self._valid_coordinate(point):
                    return {"type": "Point", "coordinates": [point[0], point[1]]}
        return None

    def _representative_point(self, geometry: dict | None) -> tuple[float, float] | None:
        if not geometry:
            return None
        coordinates = geometry.get("coordinates")
        if geometry.get("type") == "Point" and self._valid_coordinate(coordinates):
            return (float(coordinates[0]), float(coordinates[1]))
        flat = self._flatten_coordinates(coordinates)
        if not flat:
            return None
        return (sum(point[0] for point in flat) / len(flat), sum(point[1] for point in flat) / len(flat))

    def _flatten_coordinates(self, value: object) -> list[tuple[float, float]]:
        if self._valid_coordinate(value):
            return [(float(value[0]), float(value[1]))]
        if isinstance(value, list):
            return [point for item in value for point in self._flatten_coordinates(item)]
        return []

    def _valid_coordinate(self, value: object) -> bool:
        return (
            isinstance(value, list | tuple)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
            and not isinstance(value[0], bool)
            and not isinstance(value[1], bool)
            and -180 <= float(value[0]) <= 180
            and -90 <= float(value[1]) <= 90
        )


gis_service = GisService()
