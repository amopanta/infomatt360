from pydantic import BaseModel


class ExternalDataSourceCreate(BaseModel):
    project_id: str
    name: str
    source_type: str = "csv_url"
    source_url: str
    key_field: str = "id"
    sync_mode: str = "on_open"
    status: str = "active"


class ExternalDataSourceRead(ExternalDataSourceCreate):
    id: str


class FormDataSourceBindingCreate(BaseModel):
    template_id: str
    data_source_id: str
    alias: str
    filter_json: str | None = None


class FormDataSourceBindingRead(FormDataSourceBindingCreate):
    id: str


class BulkPublishRequest(BaseModel):
    project_id: str
    action: str
    target_template_ids: list[str]


class BulkPublishRead(BaseModel):
    id: str
    project_id: str
    action: str
    target_template_ids_json: str
    status: str
    result_json: str | None = None
