from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

from app.core.field_types import normalize_field_type


class BuilderTemplateCreate(BaseModel):
    """Entrada para crear una plantilla visual dentro de un proyecto."""

    project_id: str
    name: str
    description: str | None = None
    status: str = "draft"
    theme_json: str | None = None


class BuilderTemplateRead(BuilderTemplateCreate):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None
    owner_name: str | None = None
    submissions_count: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    availability: str = "draft"
    accepting_responses: bool = False
    participant_source: ParticipantSource | None = None


class ParticipantSource(BaseModel):
    mode: Literal["all", "list", "filter", "form"] = "all"
    participant_ids: list[str] = Field(default_factory=list)
    municipality: str | None = None
    previous_template_id: str | None = None
    required_status: str = "submitted"

    @model_validator(mode="after")
    def validate_source(self):
        if self.mode == "list" and not self.participant_ids:
            raise ValueError("Selecciona al menos un participante")
        if self.mode == "filter" and not self.municipality:
            raise ValueError("Indica el municipio")
        if self.mode == "form" and not self.previous_template_id:
            raise ValueError("Selecciona el formulario anterior")
        return self


class ParticipantSourceUpdate(BaseModel):
    source: ParticipantSource


class BuilderTemplateStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|published|paused|archived)$")


class BuilderTemplatePropertiesUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    theme_json: str | None = None


class BuilderTemplateScheduleUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class BuilderComponentCreate(BaseModel):
    """Entrada para crear un campo del constructor.

    column_id permite ubicar el componente dentro del layout visual. Es
    opcional para permitir componentes en borrador antes de ubicarlos.
    """

    template_id: str
    column_id: str | None = None
    component_type: str
    name: str
    label: str
    config_json: str | None = None
    rules_json: str | None = None
    sort_order: int = 0

    @field_validator("component_type")
    @classmethod
    def validate_component_type(cls, value: str) -> str:
        return normalize_field_type(value)


class BuilderComponentRead(BuilderComponentCreate):
    id: str


class BuilderComponentPropertiesUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=220)
    name: str = Field(min_length=1, max_length=120)
    config_json: str | None = None


class BuilderVersionCreate(BaseModel):
    """Entrada para guardar una version JSON del formulario."""

    template_id: str
    version_number: int = 1
    schema_content: str = Field(alias="schema_json")
    status: str = "draft"


class BuilderVersionRead(BuilderVersionCreate):
    id: str
