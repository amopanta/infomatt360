from pydantic import BaseModel


class BuilderTemplateCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    status: str = "draft"


class BuilderTemplateRead(BuilderTemplateCreate):
    id: str


class BuilderComponentCreate(BaseModel):
    template_id: str
    component_type: str
    name: str
    label: str
    config_json: str | None = None
    rules_json: str | None = None
    sort_order: int = 0


class BuilderComponentRead(BuilderComponentCreate):
    id: str


class BuilderVersionCreate(BaseModel):
    template_id: str
    version_number: int = 1
    schema_json: str
    status: str = "draft"


class BuilderVersionRead(BuilderVersionCreate):
    id: str
