from datetime import datetime

from pydantic import BaseModel, Field


class BuilderPublicLinkCreate(BaseModel):
    template_id: str
    label: str | None = None
    max_submissions: int | None = Field(default=None, ge=1)
    expires_in_hours: int | None = Field(default=None, ge=1, le=8760)


class BuilderPublicLinkRead(BaseModel):
    id: str
    project_id: str
    template_id: str
    label: str | None = None
    max_submissions: int | None = None
    submission_count: int
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class BuilderPublicLinkIssued(BuilderPublicLinkRead):
    """El token crudo solo viaja en la respuesta de creacion; nunca se
    vuelve a recuperar despues (mismo patron que `EmergencyAccessKeyIssued`)."""

    token: str
