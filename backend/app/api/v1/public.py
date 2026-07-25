"""Endpoints publicos, sin autenticacion.

Se usan para pre-carga de configuracion (marca blanca) antes de iniciar
sesion, tanto en la web como en un futuro PWA offline-first.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.organization import PublicBrandingRead
from app.services.organization_service import LOGO_ALLOWED_TYPES, find_logo_file, organization_service

router = APIRouter()


@router.get("/branding", response_model=PublicBrandingRead, summary="Consultar marca blanca por slug de organizacion")
def get_public_branding(slug: str, db: Session = Depends(get_db)) -> PublicBrandingRead:
    branding = organization_service.get_public_branding_by_slug(db, slug)
    if branding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")
    return branding


@router.get("/branding-logo/{organization_id}", summary="Servir el logo de la organizacion")
def get_branding_logo(organization_id: str) -> Response:
    """Publico por el mismo criterio que /branding: el logo se muestra antes
    de iniciar sesion (pantalla de login, PWA) y no revela nada sensible.
    """
    logo_file = find_logo_file(organization_id)
    if logo_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La organizacion no tiene logo cargado")
    media_type = next((mime for mime, ext in LOGO_ALLOWED_TYPES.items() if ext == logo_file.suffix), "application/octet-stream")
    return Response(content=logo_file.read_bytes(), media_type=media_type, headers={"Cache-Control": "public, max-age=300"})
