import json
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class GisLayerCreate(BaseModel):
    project_id: str
    name: str
    layer_type: str
    style_json: str | None = None
    status: str = "active"


class GisLayerRead(GisLayerCreate):
    id: str


class GisFeatureCreate(BaseModel):
    project_id: str
    layer_id: str | None = None
    participant_id: str | None = None
    record_id: str | None = None
    feature_type: Literal["Point", "LineString", "Polygon"]
    latitude: str | None = None
    longitude: str | None = None
    geometry_json: str | None = None
    properties_json: str | None = None
    status: str = "active"

    @field_validator("feature_type", mode="before")
    @classmethod
    def normalize_feature_type(cls, value: str) -> str:
        aliases = {"point": "Point", "gps": "Point", "linestring": "LineString", "geotrace": "LineString", "polygon": "Polygon", "geoshape": "Polygon"}
        return aliases.get(str(value).strip().lower(), value)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: str | None) -> str | None:
        if value is not None and not -90 <= float(value) <= 90:
            raise ValueError("Latitud fuera de rango")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: str | None) -> str | None:
        if value is not None and not -180 <= float(value) <= 180:
            raise ValueError("Longitud fuera de rango")
        return value

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.geometry_json:
            try:
                geometry = json.loads(self.geometry_json)
            except json.JSONDecodeError as exc:
                raise ValueError("geometry_json debe contener JSON valido") from exc
            if not isinstance(geometry, dict) or geometry.get("type") != self.feature_type or not isinstance(geometry.get("coordinates"), list):
                raise ValueError("GeoJSON incompatible con feature_type")
            coordinates = geometry["coordinates"]
            if self.feature_type == "Point" and not self._valid_coordinate(coordinates):
                raise ValueError("GeoJSON Point requiere una coordenada valida")
            if self.feature_type == "LineString" and (len(coordinates) < 2 or not all(self._valid_coordinate(item) for item in coordinates)):
                raise ValueError("GeoJSON LineString requiere al menos dos coordenadas validas")
            if self.feature_type == "Polygon":
                ring = coordinates[0] if coordinates and isinstance(coordinates[0], list) else []
                if len(ring) < 4 or ring[0] != ring[-1] or not all(self._valid_coordinate(item) for item in ring):
                    raise ValueError("GeoJSON Polygon requiere un anillo cerrado con tres vertices validos")
        return self

    @staticmethod
    def _valid_coordinate(value: object) -> bool:
        return (
            isinstance(value, list)
            and len(value) >= 2
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value[:2])
            and -180 <= value[0] <= 180
            and -90 <= value[1] <= 90
        )


class GisFeatureRead(GisFeatureCreate):
    id: str


class GisMapFeature(BaseModel):
    id: str
    project_id: str
    source: Literal["gis", "runtime"]
    feature_type: Literal["Point", "LineString", "Polygon"]
    latitude: float
    longitude: float
    label: str
    template_id: str | None = None
    template_name: str | None = None
    record_id: str | None = None
    field_name: str | None = None
    geometry_json: str | None = None
    properties_json: str | None = None


class GisProjectMap(BaseModel):
    project_id: str
    features: list[GisMapFeature]
