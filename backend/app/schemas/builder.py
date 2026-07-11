from pydantic import BaseModel, Field, field_validator

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


class BuilderVersionCreate(BaseModel):
    """Entrada para guardar una version JSON del formulario."""

    template_id: str
    version_number: int = 1
    schema_content: str = Field(alias="schema_json")
    status: str = "draft"


class BuilderVersionRead(BuilderVersionCreate):
    id: str
