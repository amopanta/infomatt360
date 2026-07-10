from datetime import datetime

from pydantic import BaseModel


class ReportCreate(BaseModel):
    project_id: str
    name: str
    report_type: str
    query_json: str
    layout_json: str | None = None
    status: str = "draft"


class ReportRead(ReportCreate):
    id: str


class ReportLinkCreate(BaseModel):
    report_id: str
    token: str
    access_mode: str = "private"
    allow_download: bool = False
    status: str = "active"


class ReportLinkRead(ReportLinkCreate):
    id: str


class ReportTemplateMetric(BaseModel):
    template_id: str
    template_name: str
    template_status: str
    records_total: int
    records_by_status: dict[str, int]
    percent_of_total: float
    last_record_at: datetime | None = None


class ReportProjectSummary(BaseModel):
    project_id: str
    records_total: int
    records_by_status: dict[str, int]
    templates: list[ReportTemplateMetric]
    generated_at: datetime
