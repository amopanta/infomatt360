from pydantic import BaseModel


class FileAssetCreate(BaseModel):
    project_id: str
    participant_id: str | None = None
    record_id: str | None = None
    asset_type: str
    original_name: str
    storage_provider: str = "local"
    storage_path: str
    mime_type: str | None = None
    size_bytes: int = 0
    checksum: str | None = None
    ocr_text: str | None = None
    metadata_json: str | None = None


class FileAssetRead(FileAssetCreate):
    id: str
    created_by: str | None = None
