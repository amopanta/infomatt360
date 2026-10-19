from datetime import datetime

from pydantic import BaseModel, Field


class ReviewActionCreate(BaseModel):
    project_id: str
    record_id: str
    to_status: str = Field(pattern="^[a-z0-9_]{1,60}$")
    action: str = Field(min_length=1, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    rejected_field_name: str | None = Field(default=None, max_length=180)


class ReopenApprovedRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
    # Excepción administrativa: quién corrige (por defecto, el autor)
    assignee_user_id: str | None = None


class ObservationIn(BaseModel):
    field_name: str | None = Field(default=None, max_length=180)
    repeat_path: str | None = Field(default=None, max_length=300)
    evidence_file_id: str | None = None
    reason: str = Field(min_length=3, max_length=4000)
    requested_action: str | None = Field(default=None, max_length=300)
    client_ref: str | None = Field(default=None, max_length=120)


class ReturnRecordRequest(BaseModel):
    notes: str = Field(min_length=3, max_length=2000)
    # Vacío = devolver al autor original; con valor = reasignar la corrección
    assignee_user_id: str | None = None
    observations: list[ObservationIn] = Field(default_factory=list, max_length=200)


class ObservationUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_correction|corrected|verified|rejected)$")
    note: str | None = Field(default=None, max_length=4000)


class ReviewActionRead(ReviewActionCreate):
    id: str
    from_status: str | None = None
    user_id: str
    approval_flow_id: str | None = None
    approval_flow_version: int | None = None
    created_at: datetime | None = None
