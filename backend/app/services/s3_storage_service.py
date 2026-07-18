"""Boveda segura de multimedia sobre S3/MinIO.

Inactivo por defecto: sin credenciales conectadas para un proyecto
(`StorageProfile.provider == "s3"` con `credentials_json`), el archivo se
sube a disco local como siempre (ver `file_service.upload`). Las imagenes
recibidas se convierten a WebP antes de calcular el hash SHA-256 y subirlas,
igual que describe la especificacion original: "convirtiendola dinamicamente
al formato de alta eficiencia WebP... calcula un hash SHA-256 unico para
blindar el archivo contra alteraciones fisicas".
"""

import hashlib
import io
import json

import boto3
from botocore.config import Config as BotoConfig
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.security import decrypt_text, encrypt_text
from app.models.storage import StorageProfile
from app.schemas.storage import S3StorageProfileConnect, StorageProfileRead
from app.services.storage_service import to_read

WEBP_CONVERTIBLE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/bmp", "image/tiff"}


class S3StorageService:
    def is_configured(self, profile: StorageProfile) -> bool:
        return bool(profile.bucket_name and profile.credentials_json)

    def connect_profile(self, db: Session, payload: S3StorageProfileConnect) -> StorageProfileRead:
        credentials = {
            "access_key_id": payload.access_key_id,
            "secret_access_key": payload.secret_access_key,
            "region": payload.region,
        }
        profile = (
            db.query(StorageProfile)
            .filter(StorageProfile.project_id == payload.project_id, StorageProfile.provider == "s3")
            .first()
        )
        if profile is None:
            profile = StorageProfile(project_id=payload.project_id, provider="s3")
            db.add(profile)
        profile.name = payload.name
        profile.bucket_name = payload.bucket_name
        profile.endpoint_url = payload.endpoint_url or None
        profile.credentials_json = encrypt_text(json.dumps(credentials))
        profile.is_default = "true" if payload.is_default else "false"
        profile.status = "active"
        db.commit()
        db.refresh(profile)
        return to_read(profile)

    def _client(self, profile: StorageProfile):
        credentials = json.loads(decrypt_text(profile.credentials_json))
        return boto3.client(
            "s3",
            aws_access_key_id=credentials["access_key_id"],
            aws_secret_access_key=credentials["secret_access_key"],
            region_name=credentials.get("region") or "us-east-1",
            endpoint_url=profile.endpoint_url or None,
            config=BotoConfig(signature_version="s3v4"),
        )

    def _maybe_convert_to_webp(self, content: bytes, mime_type: str | None, original_name: str) -> tuple[bytes, str, str]:
        if not mime_type or mime_type.lower() not in WEBP_CONVERTIBLE_MIME_TYPES:
            return content, mime_type or "application/octet-stream", original_name
        try:
            image = Image.open(io.BytesIO(content))
            image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="WEBP", quality=82)
        except (UnidentifiedImageError, OSError):
            return content, mime_type, original_name
        base_name = original_name.rsplit(".", 1)[0] if "." in original_name else original_name
        return buffer.getvalue(), "image/webp", f"{base_name}.webp"

    def upload_file(
        self,
        db: Session,
        profile: StorageProfile,
        *,
        project_id: str,
        original_name: str,
        content: bytes,
        mime_type: str | None,
    ) -> dict[str, object]:
        if not self.is_configured(profile):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El perfil de almacenamiento S3 no tiene credenciales configuradas")
        stored_content, stored_mime_type, stored_name = self._maybe_convert_to_webp(content, mime_type, original_name)
        checksum = hashlib.sha256(stored_content).hexdigest()
        key = f"{project_id}/{checksum}-{stored_name}"
        client = self._client(profile)
        try:
            client.put_object(Bucket=profile.bucket_name, Key=key, Body=stored_content, ContentType=stored_mime_type)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible subir el archivo a la boveda S3") from exc
        return {
            "storage_path": f"s3://{profile.bucket_name}/{key}",
            "mime_type": stored_mime_type,
            "original_name": stored_name,
            "size_bytes": len(stored_content),
            "checksum": checksum,
        }

    def get_object(self, profile: StorageProfile, storage_path: str) -> bytes:
        if not self.is_configured(profile):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El perfil de almacenamiento S3 no tiene credenciales configuradas")
        bucket, key = storage_path.removeprefix("s3://").split("/", 1)
        client = self._client(profile)
        try:
            response = client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No fue posible descargar el archivo desde la boveda S3") from exc


s3_storage_service = S3StorageService()
