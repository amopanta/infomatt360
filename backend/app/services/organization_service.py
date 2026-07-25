from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.organization import Organization, OrganizationBranding
from app.schemas.organization import (
    OrganizationBrandingRead,
    OrganizationBrandingUpdate,
    OrganizationCreate,
    OrganizationRead,
    PublicBrandingRead,
)

# Subida del logo de organizacion (docs/122). Solo formatos de imagen raster
# seguros para servir publicamente e incrustar en PDF (SVG excluido a
# proposito: puede contener scripts si el navegador lo abre directo).
LOGO_ALLOWED_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
LOGO_MAX_BYTES = 2 * 1024 * 1024
# Marcador estable en la URL guardada -- lo usan el endpoint publico que
# sirve el archivo y acta_service para resolverlo como archivo local.
LOGO_URL_PATH = "/api/v1/public/branding-logo/"


def _logo_directory() -> Path:
    return Path(settings.upload_directory) / "branding"


def find_logo_file(organization_id: str) -> Path | None:
    """Archivo de logo en disco para una organizacion, o None si no hay."""
    directory = _logo_directory()
    for extension in LOGO_ALLOWED_TYPES.values():
        candidate = directory / f"{organization_id}{extension}"
        if candidate.is_file():
            return candidate
    return None


def logo_file_for_url(logo_url: str | None) -> Path | None:
    """Si la URL apunta al endpoint propio de logos, devuelve el archivo local."""
    if not logo_url or LOGO_URL_PATH not in logo_url:
        return None
    organization_id = logo_url.split(LOGO_URL_PATH, 1)[1].split("?", 1)[0].strip("/")
    if not organization_id:
        return None
    return find_logo_file(organization_id)


def _to_read(row: Organization) -> OrganizationRead:
    return OrganizationRead(id=row.id, name=row.name, slug=row.slug, status=row.status)


def _branding_to_read(row: OrganizationBranding) -> OrganizationBrandingRead:
    return OrganizationBrandingRead(
        organization_id=row.organization_id,
        logo_url=row.logo_url,
        primary_color=row.primary_color,
        accent_color=row.accent_color,
        background_color=row.background_color,
        slogan=row.slogan,
    )


class OrganizationService:
    def create_organization(self, db: Session, payload: OrganizationCreate) -> OrganizationRead:
        existing = db.query(Organization).filter(Organization.slug == payload.slug).first()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug de organizacion ya existe")
        row = Organization(name=payload.name, slug=payload.slug, status=payload.status.value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_organizations(self, db: Session) -> list[OrganizationRead]:
        rows = db.query(Organization).order_by(Organization.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def get_organization(self, db: Session, organization_id: str) -> OrganizationRead | None:
        row = db.query(Organization).filter(Organization.id == organization_id).first()
        return _to_read(row) if row else None

    def get_by_slug(self, db: Session, slug: str) -> Organization | None:
        return db.query(Organization).filter(Organization.slug == slug).first()

    def upsert_branding(self, db: Session, organization_id: str, payload: OrganizationBrandingUpdate) -> OrganizationBrandingRead:
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if organization is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")
        row = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization_id).first()
        if row is None:
            row = OrganizationBranding(organization_id=organization_id)
            db.add(row)
        row.logo_url = payload.logo_url
        row.primary_color = payload.primary_color
        row.accent_color = payload.accent_color
        row.background_color = payload.background_color
        row.slogan = payload.slogan
        row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return _branding_to_read(row)

    def save_logo(self, db: Session, organization_id: str, content: bytes, content_type: str | None, base_url: str) -> OrganizationBrandingRead:
        """Guarda el logo en disco y apunta logo_url al endpoint publico.

        A diferencia de upsert_branding (que pisa todos los campos), esto solo
        toca logo_url -- los colores y el eslogan ya configurados se preservan.
        """
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if organization is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        extension = LOGO_ALLOWED_TYPES.get(normalized_type)
        if extension is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Formato de logo no soportado (use PNG, JPEG o WebP)")
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El archivo de logo esta vacio")
        if len(content) > LOGO_MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El logo supera el maximo de {LOGO_MAX_BYTES // (1024 * 1024)}MB")

        directory = _logo_directory()
        directory.mkdir(parents=True, exist_ok=True)
        # Un solo archivo por organizacion: al cambiar de formato se elimina
        # el anterior para no dejar huerfanos ambiguos.
        for other_extension in LOGO_ALLOWED_TYPES.values():
            leftover = directory / f"{organization_id}{other_extension}"
            if other_extension != extension and leftover.is_file():
                leftover.unlink()
        (directory / f"{organization_id}{extension}").write_bytes(content)

        row = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization_id).first()
        if row is None:
            row = OrganizationBranding(organization_id=organization_id)
            db.add(row)
        # ?v= por updated_at para que navegadores no muestren un logo viejo cacheado.
        row.logo_url = f"{base_url.rstrip('/')}{LOGO_URL_PATH}{organization_id}?v={int(utc_now().timestamp())}"
        row.updated_at = utc_now()
        db.commit()
        db.refresh(row)
        return _branding_to_read(row)

    def get_branding(self, db: Session, organization_id: str) -> OrganizationBrandingRead | None:
        row = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization_id).first()
        return _branding_to_read(row) if row else None

    def get_public_branding_by_slug(self, db: Session, slug: str) -> PublicBrandingRead | None:
        organization = self.get_by_slug(db, slug)
        if organization is None:
            return None
        branding = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization.id).first()
        return PublicBrandingRead(
            organization_name=organization.name,
            logo_url=branding.logo_url if branding else None,
            primary_color=branding.primary_color if branding else None,
            accent_color=branding.accent_color if branding else None,
            background_color=branding.background_color if branding else None,
            slogan=branding.slogan if branding else None,
        )


organization_service = OrganizationService()
