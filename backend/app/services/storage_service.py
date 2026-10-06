from sqlalchemy.orm import Session

from app.models.storage import StorageProfile
from fastapi import HTTPException
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
        max_file_size_mb=row.max_file_size_mb,
        is_default=row.is_default == "true",
        status=row.status,
    )


class StorageService:
    def set_default(self, db: Session, project_id: str, profile_id: str) -> StorageProfileRead:
        profile = db.query(StorageProfile).filter_by(id=profile_id, project_id=project_id, status="active").first()
        if profile is None:
            raise HTTPException(status_code=404, detail="Destino de almacenamiento no encontrado o inactivo")
        if profile.provider == "gdrive" and not profile.oauth_tokens_encrypted:
            raise HTTPException(status_code=422, detail="Conecta Google Drive antes de activarlo")
        if profile.provider == "s3" and not profile.credentials_json:
            raise HTTPException(status_code=422, detail="Conecta S3 antes de activarlo")
        db.query(StorageProfile).filter_by(project_id=project_id).update({"is_default": "false"})
        profile.is_default = "true"
        db.commit()
        db.refresh(profile)
        return to_read(profile)

    def create_profile(self, db: Session, payload: StorageProfileCreate) -> StorageProfileRead:
        if payload.is_default:
            db.query(StorageProfile).filter_by(project_id=payload.project_id).update({"is_default": "false"})
        row = StorageProfile(
            project_id=payload.project_id,
            name=payload.name,
            provider=payload.provider,
            base_path=payload.base_path,
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

