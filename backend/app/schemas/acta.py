from datetime import datetime

from pydantic import BaseModel, Field


class ActaTemplateCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=3)
    html_template: str = Field(..., min_length=1)


class ActaTemplateRead(ActaTemplateCreate):
    id: str
    created_at: datetime
    updated_at: datetime


class ActaRenderRequest(BaseModel):
    data: dict[str, str] = Field(default_factory=dict)
