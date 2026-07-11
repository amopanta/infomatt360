import secrets
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_api_key_secret, verify_api_key_secret
from app.core.time import utc_now
from app.models.api_key import ProjectApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyRead


@dataclass(frozen=True)
class ParsedApiKey:
    key_id: str
    secret: str


def _permissions_to_text(permissions: list[str]) -> str:
    clean = [item.strip() for item in permissions if item.strip()]
    return ",".join(dict.fromkeys(clean))


def _permissions_from_text(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def to_read(row: ProjectApiKey) -> ApiKeyRead:
    return ApiKeyRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        key_id=row.key_id,
        permissions=_permissions_from_text(row.permissions),
        rate_limit_profile=row.rate_limit_profile,
        status=row.status,
        created_by=row.created_by,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


class ApiKeyService:
    prefix = "im360"

    def create_key(self, db: Session, payload: ApiKeyCreate, created_by: str) -> ApiKeyCreateResponse:
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
        permissions = set(_permissions_from_text(row.permissions))
        if required_permission and required_permission not in permissions:
            return None
        row.last_used_at = utc_now()
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
