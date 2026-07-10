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
    status: str
    theme_json: str | None = None
    pages: list[RuntimePage] = []
