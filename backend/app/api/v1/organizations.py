from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_any_permission, require_permission_in_organization
from app.core.permissions import ORGANIZATIONS_BRANDING_MANAGE, ORGANIZATIONS_MANAGE, ORGANIZATIONS_TENANT_CLEAN
from app.db.session import get_db
from app.models.identity import User
from app.models.organization import Organization
from app.schemas.governance import TenantCleanRequest, TenantCleanResult
from app.schemas.organization import (
    OrganizationBrandingRead,
    OrganizationBrandingUpdate,
    OrganizationCreate,
    OrganizationRead,
)
from app.services.governance_service import governance_service
from app.services.mfa_service import mfa_service
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


@router.post(
    "/{organization_id}/tenant-clean",
    response_model=TenantCleanResult,
    summary="Purga controlada de datos de prueba de una organizacion (accion critica)",
)
def tenant_clean(
    organization_id: str,
    payload: TenantCleanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantCleanResult:
    require_permission_in_organization(db, current_user.id, organization_id, ORGANIZATIONS_TENANT_CLEAN)

    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")
    if payload.confirm_slug != organization.slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La confirmacion no coincide con el slug de la organizacion")

    if not current_user.mfa_enabled or not mfa_service.verify_totp(current_user, payload.totp_code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere un codigo 2FA valido para esta accion critica")

    result = governance_service.tenant_clean(db, organization_id)
    return TenantCleanResult(**result)
