from enum import Enum

from pydantic import BaseModel, Field


class OrganizationStatus(str, Enum):
    active = "active"
    suspended = "suspended"


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2)
    slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    status: OrganizationStatus = OrganizationStatus.active


class OrganizationRead(OrganizationCreate):
    id: str


class OrganizationBrandingUpdate(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    slogan: str | None = None


class OrganizationBrandingRead(OrganizationBrandingUpdate):
    organization_id: str


class PublicBrandingRead(BaseModel):
    """Respuesta minima y sin datos sensibles para pre-carga (web y PWA) antes de iniciar sesion."""

    organization_name: str
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    slogan: str | None = None
