"""Rutas del instalador de primer arranque.

Sin autenticacion: por diseno, se usan antes de que exista ningun usuario en
el sistema. `installation_service.bootstrap` rechaza con 409 si el sistema
ya fue instalado, y con el flag `installer_enforced` desactivado el sistema
se reporta siempre como instalado.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.installation import InstallBootstrapRequest, InstallBootstrapResponse, InstallStatusResponse
from app.services.installation_service import installation_service

router = APIRouter()


@router.get("/status", response_model=InstallStatusResponse, summary="Consultar estado de instalacion")
def get_install_status(db: Session = Depends(get_db)) -> InstallStatusResponse:
    return installation_service.status(db)


@router.post("/bootstrap", response_model=InstallBootstrapResponse, summary="Completar instalacion de primer arranque")
def bootstrap_installation(payload: InstallBootstrapRequest, db: Session = Depends(get_db)) -> InstallBootstrapResponse:
    return installation_service.bootstrap(db, payload)
