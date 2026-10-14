from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeviceAssignmentCreate(BaseModel):
    user_id: str
    device_fingerprint: str = Field(min_length=1, max_length=200)
    device_name: str = Field(default="", max_length=200)
    device_os: str = Field(default="", max_length=60)
    device_model: str = Field(default="", max_length=120)
    app_version: str = Field(default="", max_length=30)
    notes: str | None = None


class DeviceAssignmentUpdate(BaseModel):
    status: Literal["active", "revoked"] | None = None
    device_name: str | None = Field(default=None, max_length=200)
    app_version: str | None = Field(default=None, max_length=30)
    notes: str | None = None
    last_sync_at: datetime | None = None


class DeviceAssignmentRead(BaseModel):
    id: str
    user_id: str
    project_id: str
    device_fingerprint: str
    device_name: str
    device_os: str
    device_model: str
    app_version: str
    status: str
    notes: str | None
    last_sync_at: datetime | None
    registered_by: str
    created_at: datetime
    updated_at: datetime
