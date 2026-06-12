from sqlalchemy.orm import Session

from app.models.files import FileAsset
from app.schemas.files import FileAssetCreate, FileAssetRead


def to_read(row: FileAsset) -> FileAssetRead:
    return FileAssetRead(
        id=row.id,
        project_id=row.project_id,
        participant_id=row.participant_id,
        record_id=row.record_id,
        asset_type=row.asset_type,
        original_name=row.original_name,
        storage_provider=row.storage_provider,
        storage_path=row.storage_path,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        checksum=row.checksum,
        ocr_text=row.ocr_text,
        metadata_json=row.metadata_json,
        created_by=row.created_by,
    )


class FileService:
    def create_asset(self, db: Session, payload: FileAssetCreate, user_id: str) -> FileAssetRead:
        row = FileAsset(**payload.model_dump(), created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_assets(self, db: Session, project_id: str, participant_id: str | None = None, record_id: str | None = None) -> list[FileAssetRead]:
        query = db.query(FileAsset).filter(FileAsset.project_id == project_id)
        if participant_id:
            query = query.filter(FileAsset.participant_id == participant_id)
        if record_id:
            query = query.filter(FileAsset.record_id == record_id)
        rows = query.order_by(FileAsset.created_at.desc()).all()
        return [to_read(row) for row in rows]


file_service = FileService()
