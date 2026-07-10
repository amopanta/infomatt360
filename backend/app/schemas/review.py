from datetime import datetime

from pydantic import BaseModel, Field


class ReviewActionCreate(BaseModel):
    project_id: str
    record_id: str
    to_status: str = Field(pattern="^[a-z0-9_]{1,60}$")
    action: str = Field(min_length=1, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)


class ReviewActionRead(ReviewActionCreate):
    id: str
    from_status: str | None = None
    user_id: str
    approval_flow_id: str | None = None
    approval_flow_version: int | None = None
    created_at: datetime | None = None
