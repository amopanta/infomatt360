from sqlalchemy.orm import Session

from app.models.storage import StorageProfile
from app.schemas.storage import StorageProfileCreate, StorageProfileRead


def to_read(row: StorageProfile) -> StorageProfileRead:
    return StorageProfileRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        provider=row.provider,
        base_path=row.base_path,
        bucket_name=row.bucket_name,
        endpoint_url=row.endpoint_url,
        credentials_json=row.credentials_json,
        max_file_size_mb=row.max_file_size_mb,
        is_default=row.is_default == "true",
        status=row.status,
    )


class StorageService:
    def create_profile(self, db: Session, payload: StorageProfileCreate) -> StorageProfileRead:
        row = StorageProfile(
            project_id=payload.project_id,
            name=payload.name,
            provider=payload.provider,
            base_path=payload.base_path,
            bucket_name=payload.bucket_name,
            endpoint_url=payload.endpoint_url,
            credentials_json=payload.credentials_json,
            max_file_size_mb=payload.max_file_size_mb,
            is_default="true" if payload.is_default else "false",
            status=payload.status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_profiles(self, db: Session, project_id: str) -> list[StorageProfileRead]:
        rows = db.query(StorageProfile).filter(StorageProfile.project_id == project_id).order_by(StorageProfile.created_at.desc()).all()
        return [to_read(row) for row in rows]


storage_service = StorageService()
