from pydantic import BaseModel


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
    feature_type: str
    latitude: str | None = None
    longitude: str | None = None
    geometry_json: str | None = None
    properties_json: str | None = None
    status: str = "active"


class GisFeatureRead(GisFeatureCreate):
    id: str
