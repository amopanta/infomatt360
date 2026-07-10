from pydantic import BaseModel, Field


class QrGenerateRequest(BaseModel):
    project_id: str
    user_id: str
    expires_in_minutes: int = Field(default=15, ge=1, le=120)


class QrValidateRequest(BaseModel):
    token: str
    device_fingerprint: str | None = None


class QrValidateResponse(BaseModel):
    valid: bool
    project_id: str | None = None
    user_id: str | None = None
