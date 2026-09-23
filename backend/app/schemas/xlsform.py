from pydantic import BaseModel, Field
from datetime import datetime


class XlsformImportResult(BaseModel):
    template_id: str
    imported_fields: int
    warnings: list[str] = Field(default_factory=list)
    replaced: bool = False


class FormVersionSummary(BaseModel):
    id: str
    version_number: int
    status: str
    created_at: datetime
    question_count: int


class FormFieldChange(BaseModel):
    name: str
    changes: list[str] = Field(default_factory=list)


class XlsformPreview(BaseModel):
    format: str
    filename: str
    file_sha256: str
    target_sha256: str | None = None
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[FormFieldChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
