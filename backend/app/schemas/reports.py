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
