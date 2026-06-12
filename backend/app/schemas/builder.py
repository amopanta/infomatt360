from pydantic import BaseModel


class BuilderTemplateCreate(BaseModel):
    """Entrada para crear una plantilla visual dentro de un proyecto."""

    project_id: str
    name: str
    description: str | None = None
    status: str = "draft"


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


class BuilderComponentRead(BuilderComponentCreate):
    id: str


class BuilderVersionCreate(BaseModel):
    """Entrada para guardar una version JSON del formulario."""

    template_id: str
    version_number: int = 1
    schema_json: str
    status: str = "draft"


class BuilderVersionRead(BuilderVersionCreate):
    id: str
