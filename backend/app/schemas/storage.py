from pydantic import BaseModel


class StorageProfileCreate(BaseModel):
    project_id: str
    name: str
    provider: str = "local"
    base_path: str | None = None
    max_file_size_mb: int = 25
    is_default: bool = False
    status: str = "active"


class StorageProfileRead(BaseModel):
    id: str
    project_id: str
    name: str
    provider: str
    base_path: str | None = None
    bucket_name: str | None = None
    endpoint_url: str | None = None
    max_file_size_mb: int
    is_default: bool
    status: str


class S3StorageProfileConnect(BaseModel):
    project_id: str
    name: str = "S3 / MinIO"
    bucket_name: str
    endpoint_url: str | None = None
    region: str = "us-east-1"
    access_key_id: str
    secret_access_key: str
    is_default: bool = True
