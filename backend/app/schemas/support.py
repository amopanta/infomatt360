from datetime import datetime

from pydantic import BaseModel


class SupportTicketCreate(BaseModel):
    project_id: str
    subject: str
    description: str


class SupportTicketRead(BaseModel):
    id: str
    project_id: str
    created_by: str
    subject: str
    description: str
    status: str
    resolution_channel: str
    matched_rule: str | None = None
    auto_response_text: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class SupportTicketResolve(BaseModel):
    resolution_note: str | None = None
