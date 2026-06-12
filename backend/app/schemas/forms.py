from pydantic import BaseModel


class FormFieldCreate(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool = False
    layout_row: int = 1
    layout_col: int = 1
    options_json: str | None = None
    rules_json: str | None = None


class FormFieldRead(FormFieldCreate):
    id: str


class FormCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    fields: list[FormFieldCreate] = []


class FormRead(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None = None
    status: str
    current_version: int
    fields: list[FormFieldRead] = []
