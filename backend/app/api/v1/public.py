"""Endpoints publicos, sin autenticacion.

Se usan para pre-carga de configuracion (marca blanca) antes de iniciar
sesion, tanto en la web como en un futuro PWA offline-first.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.organization import PublicBrandingRead
from app.services.organization_service import organization_service

router = APIRouter()


@router.get("/branding", response_model=PublicBrandingRead, summary="Consultar marca blanca por slug de organizacion")
def get_public_branding(slug: str, db: Session = Depends(get_db)) -> PublicBrandingRead:
    branding = organization_service.get_public_branding_by_slug(db, slug)
    if branding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")
    return branding
