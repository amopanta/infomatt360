from datetime import datetime

from pydantic import BaseModel


class DashboardRecentRecord(BaseModel):
    id: str
    template_id: str
    template_name: str
    status: str
    submitted_by: str | None = None
    created_at: datetime


class DashboardSummary(BaseModel):
    project_id: str
    templates_total: int
    published_templates: int
    records_total: int
    users_total: int
    files_total: int
    storage_bytes: int
    records_by_status: dict[str, int]
    recent_records: list[DashboardRecentRecord]
