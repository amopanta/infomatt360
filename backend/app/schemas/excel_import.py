from datetime import datetime

from pydantic import BaseModel


class ExcelImportPreview(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, object]]


class ExcelImportTargetField(BaseModel):
    name: str
    label: str


class ExcelImportJobRead(BaseModel):
    id: str
    project_id: str
    entity_type: str
    template_id: str | None = None
    source_filename: str
    status: str
    column_mapping: dict[str, str] | None = None
    preview: ExcelImportPreview | None = None
    # Solo se completa para entity_type="records": los campos de la
    # plantilla elegida, ya filtrados a tipos escalares simples, mas los
    # dos campos reservados de metadatos (estado, fecha historica). El
    # frontend lo usa para pintar el selector de mapeo en vez de una lista
    # fija de campos destino (ver docs/104).
    target_fields: list[ExcelImportTargetField] | None = None
    total_rows: int
    imported_rows: int
    failed_rows: int
    error_report: list[dict[str, object]] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExcelImportMappingUpdate(BaseModel):
    column_mapping: dict[str, str]
