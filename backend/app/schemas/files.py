from datetime import datetime

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
    created_at: datetime


class EvidenceBatchDownloadRequest(BaseModel):
    """Selecciona el conjunto de evidencias para el ZIP (docs/96 #7): o bien
    una lista explicita de ids, o los filtros de la galeria de evidencias,
    resueltos sin paginacion contra el servidor. asset_ids, si no esta
    vacio, tiene prioridad -- nunca se combinan ambos caminos (mismo
    criterio que ActaRenderBatchRequest, ver docs/110)."""

    asset_ids: list[str] | None = None
    participant_id: str | None = None
    template_id: str | None = None
    status: str | None = None
    created_by: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
