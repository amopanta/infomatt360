from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission
from app.core.permissions import ORGANIZATIONS_BRANDING_MANAGE, ORGANIZATIONS_MANAGE
from app.db.session import get_db
from app.models.identity import User
from app.schemas.organization import (
    OrganizationBrandingRead,
    OrganizationBrandingUpdate,
    OrganizationCreate,
    OrganizationRead,
)
from app.services.organization_service import organization_service

router = APIRouter()


@router.post("/", response_model=OrganizationRead, summary="Crear organizacion")
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrganizationRead:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return organization_service.create_organization(db, payload)


@router.get("/", response_model=list[OrganizationRead], summary="Listar organizaciones")
def list_organizations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[OrganizationRead]:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_MANAGE})
    return organization_service.list_organizations(db)


@router.put("/{organization_id}/branding", response_model=OrganizationBrandingRead, summary="Configurar marca blanca de la organizacion")
def update_branding(organization_id: str, payload: OrganizationBrandingUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrganizationBrandingRead:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_BRANDING_MANAGE, ORGANIZATIONS_MANAGE})
    return organization_service.upsert_branding(db, organization_id, payload)


@router.get("/{organization_id}/branding", response_model=OrganizationBrandingRead | None, summary="Consultar marca blanca de la organizacion")
def get_branding(organization_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrganizationBrandingRead | None:
    require_any_permission(db, current_user.id, {ORGANIZATIONS_BRANDING_MANAGE, ORGANIZATIONS_MANAGE})
    return organization_service.get_branding(db, organization_id)
