from pydantic import BaseModel


class MirrorTargetCreate(BaseModel):
    project_id: str
    name: str
    engine: str
    conn_json: str | None = None
    status: str = "active"


class MirrorTargetRead(MirrorTargetCreate):
    id: str


class MirrorPlanCreate(BaseModel):
    target_id: str
    name: str
    tables_json: str
    schedule_mode: str = "manual"
    status: str = "active"


class MirrorPlanRead(MirrorPlanCreate):
    id: str
    last_result: str | None = None
