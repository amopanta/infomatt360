from pydantic import BaseModel, Field


class XlsformImportResult(BaseModel):
    template_id: str
    imported_fields: int
    warnings: list[str] = Field(default_factory=list)
    replaced: bool = False
