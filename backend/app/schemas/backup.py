from datetime import datetime

from pydantic import BaseModel


class BackupJobRead(BaseModel):
    id: str
    project_id: str
    storage_profile_id: str | None = None
    status: str
    file_path: str | None = None
    size_bytes: int | None = None
    triggered_by: str | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
