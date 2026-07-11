from datetime import datetime

from pydantic import BaseModel, Field


class EmergencyAccessKeyCreate(BaseModel):
    project_id: str
    user_id: str
    hours_valid: int = Field(default=24, ge=1, le=168)
    purpose: str | None = None


class EmergencyAccessKeyRead(BaseModel):
    id: str
    project_id: str
    user_id: str
    issued_by: str
    purpose: str | None = None
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class EmergencyAccessKeyIssued(EmergencyAccessKeyRead):
    code: str


class EmergencyAccessRedeemRequest(BaseModel):
    code: str


class EmergencyAccessRedeemResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
