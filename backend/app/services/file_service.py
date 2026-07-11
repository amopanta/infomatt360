import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.files import FileAsset
from app.models.storage import StorageProfile
from app.schemas.files import FileAssetCreate, FileAssetRead
from app.services.s3_storage_service import s3_storage_service


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

    def local_storage_config(self, db: Session, project_id: str) -> tuple[Path, int]:
        profile = (
            db.query(StorageProfile)
            .filter(
                StorageProfile.project_id == project_id,
                StorageProfile.provider == "local",
                StorageProfile.status == "active",
            )
            .order_by(StorageProfile.is_default.desc(), StorageProfile.created_at.desc())
            .first()
        )
        base_path = Path(profile.base_path if profile and profile.base_path else settings.upload_directory)
        max_size_mb = profile.max_file_size_mb if profile else settings.default_max_file_size_mb
        return base_path, max(1, max_size_mb)

    def active_s3_profile(self, db: Session, project_id: str) -> StorageProfile | None:
        return (
            db.query(StorageProfile)
            .filter(
                StorageProfile.project_id == project_id,
                StorageProfile.provider == "s3",
                StorageProfile.status == "active",
                StorageProfile.is_default == "true",
            )
            .order_by(StorageProfile.created_at.desc())
            .first()
        )

    async def upload(
        self,
        db: Session,
        *,
        project_id: str,
        asset_type: str,
        upload: UploadFile,
        user_id: str,
        participant_id: str | None = None,
        record_id: str | None = None,
    ) -> FileAssetRead:
        profile = self.active_s3_profile(db, project_id)
        if profile is not None and s3_storage_service.is_configured(profile):
            return await self.upload_s3(
                db,
                profile,
                project_id=project_id,
                asset_type=asset_type,
                upload=upload,
                user_id=user_id,
                participant_id=participant_id,
                record_id=record_id,
            )
        return await self.upload_local(
            db,
            project_id=project_id,
            asset_type=asset_type,
            upload=upload,
            user_id=user_id,
            participant_id=participant_id,
            record_id=record_id,
        )

    async def upload_s3(
        self,
        db: Session,
        profile: StorageProfile,
        *,
        project_id: str,
        asset_type: str,
        upload: UploadFile,
        user_id: str,
        participant_id: str | None = None,
        record_id: str | None = None,
    ) -> FileAssetRead:
        max_bytes = max(1, profile.max_file_size_mb) * 1024 * 1024
        original_name = Path(upload.filename or "archivo").name[:250]
        buffer = bytearray()

        try:
            while chunk := await upload.read(1024 * 1024):
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    raise ValueError(f"El archivo supera el limite de {profile.max_file_size_mb} MB")

            result = s3_storage_service.upload_file(
                db,
                profile,
                project_id=project_id,
                original_name=original_name,
                content=bytes(buffer),
                mime_type=upload.content_type,
            )
            payload = FileAssetCreate(
                project_id=project_id,
                participant_id=participant_id,
                record_id=record_id,
                asset_type=asset_type.upper(),
                original_name=result["original_name"],
                storage_provider="s3",
                storage_path=result["storage_path"],
                mime_type=result["mime_type"],
                size_bytes=result["size_bytes"],
                checksum=result["checksum"],
            )
            return self.create_asset(db, payload, user_id)
        finally:
            await upload.close()

    async def upload_local(
        self,
        db: Session,
        *,
        project_id: str,
        asset_type: str,
        upload: UploadFile,
        user_id: str,
        participant_id: str | None = None,
        record_id: str | None = None,
    ) -> FileAssetRead:
        base_path, max_size_mb = self.local_storage_config(db, project_id)
        project_directory = base_path.resolve() / project_id
        project_directory.mkdir(parents=True, exist_ok=True)

        original_name = Path(upload.filename or "archivo").name[:250]
        extension = Path(original_name).suffix.lower()[:12]
        target = project_directory / f"{uuid4()}{extension}"
        max_bytes = max_size_mb * 1024 * 1024
        size = 0
        checksum = hashlib.sha256()

        try:
            with target.open("xb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"El archivo supera el limite de {max_size_mb} MB")
                    checksum.update(chunk)
                    destination.write(chunk)

            payload = FileAssetCreate(
                project_id=project_id,
                participant_id=participant_id,
                record_id=record_id,
                asset_type=asset_type.upper(),
                original_name=original_name,
                storage_provider="local",
                storage_path=str(target),
                mime_type=upload.content_type,
                size_bytes=size,
                checksum=checksum.hexdigest(),
            )
            return self.create_asset(db, payload, user_id)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()


file_service = FileService()
