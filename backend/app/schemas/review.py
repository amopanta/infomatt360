from pydantic import BaseModel


class ReviewActionCreate(BaseModel):
    project_id: str
    record_id: str
    to_status: str
    action: str
    notes: str | None = None


class ReviewActionRead(ReviewActionCreate):
    id: str
    from_status: str | None = None
    user_id: str
