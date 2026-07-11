from pydantic import BaseModel


class IntegrationSourceCreate(BaseModel):
    project_id: str
    name: str
    source_type: str
    base_url: str | None = None
    config_json: str | None = None
    credentials: str | None = None
    status: str = "active"


class IntegrationSourceRead(BaseModel):
    """No incluye `credentials`: el secreto se cifra al guardar y nunca se
    devuelve en las respuestas de la API (mismo principio que
    `StorageProfileRead` con los tokens OAuth de Google Drive)."""

    id: str
    project_id: str
    name: str
    source_type: str
    base_url: str | None = None
    config_json: str | None = None
    status: str
    has_credentials: bool = False


class IntegrationMapCreate(BaseModel):
    source_id: str
    template_id: str | None = None
    name: str
    target_table: str
    fields_json: str
    filters_json: str | None = None
    status: str = "active"


class IntegrationMapRead(IntegrationMapCreate):
    id: str


class IntegrationJobCreate(BaseModel):
    source_id: str
    map_id: str | None = None
    mode: str = "manual"
    status: str = "pending"


class IntegrationJobRead(IntegrationJobCreate):
    id: str
    reference_record_id: str | None = None
    last_result: str | None = None
