import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_api_key_secret, verify_api_key_secret
from app.core.time import utc_now
from app.models.api_key import ProjectApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyRead


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """Normaliza a UTC sin zona, igual que utc_now() (columnas SQLAlchemy
    DateTime existentes). El frontend envia expires_at con sufijo "Z"
    (datetime consciente de zona); compararlo directo contra utc_now() sin
    normalizar lanza TypeError (naive vs. aware)."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class ParsedApiKey:
    key_id: str
    secret: str


# Ver auditoria tecnica de julio 2026, hallazgo S-003: antes de esto,
# authenticate() escribia y confirmaba (commit) en cada solicitud exitosa,
# sin excepcion. Bajo alto volumen (integraciones bulk, dispositivos de
# campo) eso presiona I/O sin necesidad real -- last_used_at es solo
# informativo, no interviene en la revocacion (que usa status/revoked_at),
# asi que una precision de un minuto es mas que suficiente.
LAST_USED_AT_WRITE_INTERVAL_SECONDS = 60


def _permissions_to_text(permissions: list[str]) -> str:
    clean = [item.strip() for item in permissions if item.strip()]
    return ",".join(dict.fromkeys(clean))


def _permissions_from_text(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _effective_status(row: ProjectApiKey) -> str:
    if row.status == "active" and row.expires_at is not None and row.expires_at <= utc_now():
        return "expired"
    return row.status


def to_read(row: ProjectApiKey) -> ApiKeyRead:
    return ApiKeyRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        key_id=row.key_id,
        permissions=_permissions_from_text(row.permissions),
        rate_limit_profile=row.rate_limit_profile,
        status=_effective_status(row),
        created_by=row.created_by,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        expires_at=row.expires_at,
    )


class ApiKeyService:
    prefix = "im360"

    def create_key(self, db: Session, payload: ApiKeyCreate, created_by: str) -> ApiKeyCreateResponse:
        expires_at = _to_naive_utc(payload.expires_at)
        if expires_at is not None and expires_at <= utc_now():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="expires_at debe ser una fecha futura")
        key_id = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
        secret = secrets.token_urlsafe(32)
        api_key = f"{self.prefix}_{key_id}_{secret}"
        row = ProjectApiKey(
            project_id=payload.project_id,
            name=payload.name,
            key_id=key_id,
            secret_hash=hash_api_key_secret(secret),
            permissions=_permissions_to_text(payload.permissions),
            rate_limit_profile=payload.rate_limit_profile,
            expires_at=expires_at,
            created_by=created_by,
            status="active",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ApiKeyCreateResponse(**to_read(row).model_dump(), api_key=api_key)

    def list_keys(self, db: Session, project_id: str) -> list[ApiKeyRead]:
        try:
            rows = db.query(ProjectApiKey).filter(ProjectApiKey.project_id == project_id).order_by(ProjectApiKey.created_at.desc()).all()
        except SQLAlchemyError:
            db.rollback()
            return []
        return [to_read(row) for row in rows]

    def revoke_key(self, db: Session, project_id: str, key_id: str) -> ApiKeyRead | None:
        row = db.query(ProjectApiKey).filter(
            ProjectApiKey.project_id == project_id,
            ProjectApiKey.key_id == key_id,
        ).first()
        if not row:
            return None
        row.status = "revoked"
        row.revoked_at = utc_now()
        db.add(row)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def authenticate(self, db: Session, raw_key: str, required_permission: str | None = None) -> ProjectApiKey | None:
        parsed = self.parse(raw_key)
        if not parsed:
            return None
        row = db.query(ProjectApiKey).filter(ProjectApiKey.key_id == parsed.key_id, ProjectApiKey.status == "active").first()
        if not row or not verify_api_key_secret(parsed.secret, row.secret_hash):
            return None
        now = utc_now()
        if row.expires_at is not None and row.expires_at <= now:
            return None
        permissions = set(_permissions_from_text(row.permissions))
        if required_permission and required_permission not in permissions:
            return None
        if row.last_used_at is None or (now - row.last_used_at).total_seconds() >= LAST_USED_AT_WRITE_INTERVAL_SECONDS:
            row.last_used_at = now
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    def rate_limit_profile_for_key(self, db: Session, raw_key: str) -> str | None:
        parsed = self.parse(raw_key)
        if not parsed:
            return None
        try:
            row = db.query(ProjectApiKey).filter(ProjectApiKey.key_id == parsed.key_id, ProjectApiKey.status == "active").first()
        except SQLAlchemyError:
            return None
        if not row or not verify_api_key_secret(parsed.secret, row.secret_hash):
            return None
        return row.rate_limit_profile

    def parse(self, raw_key: str) -> ParsedApiKey | None:
        parts = raw_key.split("_", 2)
        if len(parts) != 3 or parts[0] != self.prefix or not parts[1] or not parts[2]:
            return None
        return ParsedApiKey(key_id=parts[1], secret=parts[2])


api_key_service = ApiKeyService()
