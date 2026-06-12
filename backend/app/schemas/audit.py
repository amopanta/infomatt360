from pydantic import BaseModel


class AuditCreate(BaseModel):
    project_id: str | None = None
    module: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    before_json: str | None = None
    after_json: str | None = None
    ip_address: str | None = None
    device_info: str | None = None


class AuditRead(AuditCreate):
    id: str
    user_id: str | None = None
