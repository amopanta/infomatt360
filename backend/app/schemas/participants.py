from pydantic import BaseModel


class ParticipantCreate(BaseModel):
    project_id: str
    external_code: str | None = None
    document_id: str | None = None
    full_name: str
    participant_type: str = "person"
    status: str = "active"
    metadata_json: str | None = None


class ParticipantRead(ParticipantCreate):
    id: str
    duplicate_flag: str = "none"
