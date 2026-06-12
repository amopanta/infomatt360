from pydantic import BaseModel


class RecordCreate(BaseModel):
    project_id: str
    form_id: str
    participant_id: str | None = None
    status: str = "draft"
    source_channel: str = "web"
    payload_json: str


class RecordRead(RecordCreate):
    id: str
    created_by: str | None = None


class RecordEventRead(BaseModel):
    id: str
    record_id: str
    event_type: str
    user_id: str | None = None
    notes: str | None = None
