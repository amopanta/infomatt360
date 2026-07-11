from datetime import datetime

from pydantic import BaseModel, Field


class AiAuditConfigCreate(BaseModel):
    template_id: str
    text_field_name: str
    mode: str = Field(default="human", pattern="^(human|automatic|mixed)$")


class AiAuditConfigRead(AiAuditConfigCreate):
    id: str
    created_at: datetime


class AiCheckCreate(BaseModel):
    project_id: str
    record_id: str | None = None
    file_id: str | None = None
    check_type: str
    status: str = "pending"
    result_json: str | None = None


class AiCheckRead(AiCheckCreate):
    id: str
    created_by: str | None = None
    created_at: datetime


class OcrResultCreate(BaseModel):
    project_id: str
    file_id: str
    text_result: str | None = None
    metadata_json: str | None = None
    status: str = "pending"


class OcrResultRead(OcrResultCreate):
    id: str


class ExecutiveAnalysisCreate(BaseModel):
    project_id: str
    source_type: str
    source_id: str | None = None
    summary_text: str | None = None
    metrics_json: str | None = None
    status: str = "draft"


class ExecutiveAnalysisRead(ExecutiveAnalysisCreate):
    id: str
    created_by: str | None = None
