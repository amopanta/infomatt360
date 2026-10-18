from pydantic import BaseModel


class RuntimeComponent(BaseModel):
    id: str
    type: str
    name: str
    label: str
    config_json: str | None = None
    rules_json: str | None = None


class RuntimeColumn(BaseModel):
    id: str
    desktop_width: int
    tablet_width: int
    mobile_width: int
    components: list[RuntimeComponent] = []


class RuntimeRow(BaseModel):
    id: str
    columns: list[RuntimeColumn] = []


class RuntimeSection(BaseModel):
    id: str
    title: str
    description: str | None = None
    rows: list[RuntimeRow] = []


class RuntimePage(BaseModel):
    id: str
    title: str
    description: str | None = None
    sections: list[RuntimeSection] = []


class RuntimeTemplate(BaseModel):
    template_id: str
    name: str
    description: str | None = None
    status: str
    theme_json: str | None = None
    # legacy | open | closed (ver form_access_mode). La app de campo lo usa
    # para aplicar sin conexión las mismas reglas de asignación que el servidor.
    access_mode: str = "legacy"
    pages: list[RuntimePage] = []
