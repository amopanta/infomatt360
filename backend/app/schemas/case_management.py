from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    participant_id: str
    title: str = Field(min_length=3, max_length=180)
    assigned_user_id: str | None = None
    due_at: datetime | None = None
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    reminder_channels: list[Literal["internal", "email", "whatsapp"]] = Field(default_factory=lambda: ["internal"])


class CaseUpdate(BaseModel):
    status: Literal["open", "in_progress", "referred", "closed"] | None = None
    assigned_user_id: str | None = None
    due_at: datetime | None = None
    note: str | None = Field(default=None, max_length=4000)
    properties: dict[str, str | int | float | bool | None] | None = None
    reminder_channels: list[Literal["internal", "email", "whatsapp"]] | None = None


class CaseRead(BaseModel):
    id: str
    project_id: str
    participant_id: str
    title: str
    status: str
    assigned_user_id: str | None
    due_at: datetime | None
    properties: dict
    created_by: str
    created_at: datetime
    updated_at: datetime


class CaseEventRead(BaseModel):
    id: str
    case_id: str
    event_type: str
    note: str | None
    from_user_id: str
    to_user_id: str | None
    created_at: datetime


class TerritoryCreate(BaseModel):
    user_id: str
    department: str = Field(min_length=1, max_length=120)
    municipality: str = Field(default="", max_length=120)


class TerritoryRead(TerritoryCreate):
    id: str
    project_id: str


class SavedExportCreate(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    template_id: str | None = None
    frequency: Literal["manual", "daily", "weekly"] = "manual"
    recipient_user_id: str


class SavedExportRead(SavedExportCreate):
    id: str
    project_id: str
    last_run_at: datetime | None
