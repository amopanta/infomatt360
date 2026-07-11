from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.organization import Organization, OrganizationBranding
from app.schemas.organization import (
    OrganizationBrandingRead,
    OrganizationBrandingUpdate,
    OrganizationCreate,
    OrganizationRead,
    PublicBrandingRead,
)


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
