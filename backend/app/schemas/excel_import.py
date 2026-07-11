from datetime import datetime

from pydantic import BaseModel


class ExcelImportPreview(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, object]]


class ExcelImportJobRead(BaseModel):
    id: str
    project_id: str
    entity_type: str
    source_filename: str
    status: str
    column_mapping: dict[str, str] | None = None
    preview: ExcelImportPreview | None = None
    total_rows: int
    imported_rows: int
    failed_rows: int
    error_report: list[dict[str, object]] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExcelImportMappingUpdate(BaseModel):
    column_mapping: dict[str, str]
