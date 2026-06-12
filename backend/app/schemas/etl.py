from pydantic import BaseModel


class EtlRuleCreate(BaseModel):
    project_id: str
    name: str
    rule_type: str
    source_field: str | None = None
    target_field: str | None = None
    operator: str | None = None
    value_text: str | None = None
    config_json: str | None = None
    status: str = "active"


class EtlRuleRead(EtlRuleCreate):
    id: str


class EtlPipelineCreate(BaseModel):
    project_id: str
    name: str
    source_id: str | None = None
    steps_json: str
    status: str = "active"


class EtlPipelineRead(EtlPipelineCreate):
    id: str
