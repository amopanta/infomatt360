from pydantic import BaseModel


class StorageProfileCreate(BaseModel):
    project_id: str
    name: str
    provider: str = "local"
    base_path: str | None = None
    bucket_name: str | None = None
    endpoint_url: str | None = None
    credentials_json: str | None = None
    max_file_size_mb: int = 25
    is_default: bool = False
    status: str = "active"


class StorageProfileRead(StorageProfileCreate):
    id: str
