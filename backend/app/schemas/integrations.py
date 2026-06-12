from pydantic import BaseModel


class IntegrationSourceCreate(BaseModel):
    project_id: str
    name: str
    source_type: str
    base_url: str | None = None
    config_json: str | None = None
    status: str = "active"


class IntegrationSourceRead(IntegrationSourceCreate):
    id: str


class IntegrationMapCreate(BaseModel):
    source_id: str
    name: str
    target_table: str
    fields_json: str
    filters_json: str | None = None
    status: str = "active"


class IntegrationMapRead(IntegrationMapCreate):
    id: str


class IntegrationJobCreate(BaseModel):
    source_id: str
    map_id: str | None = None
    mode: str = "manual"
    status: str = "pending"


class IntegrationJobRead(IntegrationJobCreate):
    id: str
    last_result: str | None = None
