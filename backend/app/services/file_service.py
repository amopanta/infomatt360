import csv
import hashlib
import io
import zipfile
from datetime import datetime
from io import StringIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.files import FileAsset
from app.models.identity import User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.models.storage import StorageProfile
from app.schemas.files import FileAssetCreate, FileAssetRead
from app.services.evidence_naming import build_evidence_filename
from app.services.s3_storage_service import s3_storage_service


def _parse_s3_uri(storage_path: str) -> tuple[str, str]:
    bucket, key = storage_path.removeprefix("s3://").split("/", 1)
    return bucket, key


def _manifest_csv(rows: list[tuple[str, str, str]]) -> str:
    output = StringIO()
    output.write("﻿")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue()


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
        created_at=row.created_at,
    )


class FileService:
    def create_asset(self, db: Session, payload: FileAssetCreate, user_id: str) -> FileAssetRead:
        row = FileAsset(**payload.model_dump(), created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_assets(
        self,
        db: Session,
        project_id: str,
        participant_id: str | None = None,
        record_id: str | None = None,
        template_id: str | None = None,
        status: str | None = None,
        created_by: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[FileAssetRead]:
        query = self._filtered_assets_query(
            db,
            project_id,
            participant_id=participant_id,
            template_id=template_id,
            status=status,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
        )
        if record_id:
            query = query.filter(FileAsset.record_id == record_id)
        rows = query.order_by(FileAsset.created_at.desc()).all()
        return [to_read(row) for row in rows]

    def _filtered_assets_query(
        self,
        db: Session,
        project_id: str,
        *,
        participant_id: str | None = None,
        template_id: str | None = None,
        status: str | None = None,
        created_by: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        query = db.query(FileAsset).filter(FileAsset.project_id == project_id)
        if participant_id:
            query = query.filter(FileAsset.participant_id == participant_id)
        if created_by:
            query = query.filter(FileAsset.created_by == created_by)
        if date_from:
            query = query.filter(FileAsset.created_at >= date_from)
        if date_to:
            query = query.filter(FileAsset.created_at <= date_to)
        if template_id or status:
            # FileAsset no tiene template_id/status propios -- "formulario"/
            # "estado" del requerimiento son los del RuntimeRecord enlazado.
            # Es un INNER JOIN: archivos sin record_id nunca calzan con estos
            # filtros, comportamiento correcto (no un bug a corregir).
            query = query.join(RuntimeRecord, RuntimeRecord.id == FileAsset.record_id)
            if template_id:
                query = query.filter(RuntimeRecord.template_id == template_id)
            if status:
                query = query.filter(RuntimeRecord.status == status)
        return query

    def list_filtered_asset_ids(self, db: Session, project_id: str, **filters) -> list[str]:
        return [
            row.id
            for row in self._filtered_assets_query(db, project_id, **filters).order_by(FileAsset.created_at.desc()).all()
        ]

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

    # --- Lectura / descarga (docs/96 item #7) ---

    def read_local(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo no existe en el almacenamiento local")
        return path.read_bytes()

    def _resolve_s3_profile_for_asset(self, db: Session, asset: FileAsset) -> StorageProfile | None:
        """Resuelve el perfil por el bucket embebido en storage_path, no por
        el default actual del proyecto: el default puede haber rotado
        (nuevas credenciales/bucket) despues de que este archivo se escribio,
        y usarlo arriesgaria leer con credenciales equivocadas."""
        bucket, _ = _parse_s3_uri(asset.storage_path)
        return (
            db.query(StorageProfile)
            .filter(StorageProfile.project_id == asset.project_id, StorageProfile.provider == "s3", StorageProfile.bucket_name == bucket)
            .order_by(StorageProfile.status == "active", StorageProfile.created_at.desc())
            .first()
        )

    def read_asset_bytes(self, db: Session, asset: FileAsset) -> bytes:
        if asset.storage_provider == "s3":
            profile = self._resolve_s3_profile_for_asset(db, asset)
            if profile is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontro el perfil de almacenamiento S3 para este archivo")
            return s3_storage_service.get_object(profile, asset.storage_path)
        return self.read_local(asset.storage_path)

    def download_batch(self, db: Session, project_id: str, asset_ids: list[str]) -> bytes:
        """Genera un ZIP con las evidencias resueltas, renombradas segun el
        patron Participante_TipoEvidencia_Fecha (docs/96 #7). Un fallo
        individual no aborta el lote -- se anota en manifest.csv, mismo
        espiritu que acta_service.render_pdf_batch (docs/110)."""
        assets = db.query(FileAsset).filter(FileAsset.id.in_(asset_ids), FileAsset.project_id == project_id).all()
        assets_by_id = {asset.id: asset for asset in assets}
        participant_ids = {asset.participant_id for asset in assets if asset.participant_id}
        participant_names = {
            participant.id: participant.full_name
            for participant in (db.query(Participant).filter(Participant.id.in_(participant_ids)).all() if participant_ids else [])
        }

        buffer = io.BytesIO()
        manifest: list[tuple[str, str, str]] = [("file_id", "status", "error")]
        used_names: set[str] = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for asset_id in asset_ids:
                asset = assets_by_id.get(asset_id)
                if asset is None:
                    manifest.append((asset_id, "failed", "No encontrado en el proyecto"))
                    continue
                try:
                    content = self.read_asset_bytes(db, asset)
                    filename = build_evidence_filename(
                        participant_name=participant_names.get(asset.participant_id),
                        asset_type=asset.asset_type,
                        created_at=asset.created_at,
                        original_name=asset.original_name,
                        used=used_names,
                    )
                    archive.writestr(filename, content)
                    manifest.append((asset_id, "success", ""))
                except HTTPException as exc:
                    manifest.append((asset_id, "failed", str(exc.detail)))
            archive.writestr("manifest.csv", _manifest_csv(manifest))
        return buffer.getvalue()

    def list_uploaders(self, db: Session, project_id: str) -> list[dict[str, str]]:
        rows = (
            db.query(User.id, User.full_name)
            .join(FileAsset, FileAsset.created_by == User.id)
            .filter(FileAsset.project_id == project_id)
            .distinct()
            .order_by(User.full_name)
            .all()
        )
        return [{"id": row.id, "full_name": row.full_name} for row in rows]


file_service = FileService()
