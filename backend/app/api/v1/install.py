"""Rutas del instalador de primer arranque.

Sin autenticacion: por diseno, se usan antes de que exista ningun usuario en
el sistema. `installation_service.bootstrap` rechaza con 409 si el sistema
ya fue instalado, y con el flag `installer_enforced` desactivado el sistema
se reporta siempre como instalado.

Con `installer_enforced` activo, todo lo que cambia algo pide el código de
instalación (cabecera X-Install-Code), que solo ve quien tiene acceso al
servidor (docs/151). Con el sistema instalado, el mismo mecanismo con un
código de recuperación permite crear o recuperar un administrador.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.cli.create_admin import create_or_recover, password_problem
from app.core.config import settings
from app.db.session import get_db
from app.schemas.installation import (
    InstallBootstrapRequest,
    InstallBootstrapResponse,
    InstallCodeRequest,
    InstallCodeResponse,
    InstallDatabaseRequest,
    InstallDatabaseResponse,
    InstallMailRequest,
    InstallRecoverAdminRequest,
    InstallRecoverAdminResponse,
    InstallRequirementsResponse,
    InstallStatusResponse,
)
from app.services import install_code_service, install_setup_service
from app.services.auth_throttle_service import auth_throttle_service
from app.services.installation_service import installation_service

router = APIRouter()


def _code_kind(db: Session) -> str:
    return "recovery" if installation_service.is_installed(db) else "setup"


def _check_code(db: Session, request: Request, code: str | None, kind: str) -> None:
    # La instalación solo pide código con el asistente activo; la recuperación
    # siempre, porque da acceso de administrador a un sistema en uso.
    if kind == "setup" and not settings.installer_enforced:
        return
    ip_address = request.client.host if request.client else "unknown"
    # Diez intentos por cuarto de hora: un código de 12 caracteres no se adivina así.
    if not auth_throttle_service.record_attempt(db, "install-code", ip_address, maximum=10, window_minutes=15, block_minutes=15):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Espera 15 minutos.")
    if not install_code_service.verify(code or "", kind):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Código de instalación incorrecto o vencido.")


def require_setup_code(request: Request, db: Session = Depends(get_db), x_install_code: str | None = Header(default=None)) -> None:
    if installation_service.is_installed(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El sistema ya esta instalado")
    _check_code(db, request, x_install_code, "setup")


@router.get("/status", response_model=InstallStatusResponse, summary="Consultar estado de instalacion")
def get_install_status(db: Session = Depends(get_db)) -> InstallStatusResponse:
    return installation_service.status(db)


@router.post("/code/verify", response_model=InstallCodeResponse, summary="Comprobar el código de instalación o de recuperación")
def verify_install_code(payload: InstallCodeRequest, request: Request, db: Session = Depends(get_db)) -> InstallCodeResponse:
    kind = _code_kind(db)
    _check_code(db, request, payload.code, kind)
    return InstallCodeResponse(valid=True, kind=kind)


@router.get("/requirements", response_model=InstallRequirementsResponse, summary="Verificar requisitos del servidor antes de instalar")
def get_install_requirements(db: Session = Depends(get_db)) -> InstallRequirementsResponse:
    return installation_service.requirements(db)


@router.post("/database/test", response_model=InstallDatabaseResponse, summary="Probar una base PostgreSQL externa")
def test_install_database(payload: InstallDatabaseRequest, _: None = Depends(require_setup_code)) -> InstallDatabaseResponse:
    if payload.mode == "bundled":
        return InstallDatabaseResponse(mode="bundled")
    url = _external_url(payload)
    return InstallDatabaseResponse(mode="external", **install_setup_service.test_database(url))


@router.post("/database/apply", response_model=InstallDatabaseResponse, summary="Usar la base elegida (crea las tablas y reinicia)")
def apply_install_database(payload: InstallDatabaseRequest, _: None = Depends(require_setup_code)) -> InstallDatabaseResponse:
    if payload.mode == "bundled":
        return InstallDatabaseResponse(mode="bundled", **install_setup_service.use_bundled_database())
    return InstallDatabaseResponse(mode="external", **install_setup_service.apply_database(_external_url(payload)))


def _external_url(payload: InstallDatabaseRequest) -> str:
    if not payload.host or not payload.name or not payload.username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Indica servidor, nombre de la base y usuario.")
    return install_setup_service.database_url(payload.host.strip(), payload.port, payload.name.strip(), payload.username.strip(), payload.password, payload.sslmode)


@router.post("/mail/test", summary="Enviar un correo de prueba con estos datos")
def test_install_mail(payload: InstallMailRequest, _: None = Depends(require_setup_code)) -> dict:
    if not payload.test_recipient:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Indica a qué correo enviar la prueba.")
    install_setup_service.send_test_mail(payload.host.strip(), payload.port, payload.username.strip(), payload.password, payload.use_tls,
                                         str(payload.sender_email), str(payload.test_recipient))
    return {"sent": True}


@router.post("/mail/save", summary="Guardar el correo (servidor, usuario y contraseña)")
def save_install_mail(payload: InstallMailRequest, _: None = Depends(require_setup_code)) -> dict:
    install_setup_service.save_mail(payload.host.strip(), payload.port, payload.username.strip(), payload.password, payload.use_tls, str(payload.sender_email))
    return {"saved": True}


@router.post("/bootstrap", response_model=InstallBootstrapResponse, summary="Completar instalacion de primer arranque")
def bootstrap_installation(payload: InstallBootstrapRequest, request: Request, db: Session = Depends(get_db),
                           x_install_code: str | None = Header(default=None)) -> InstallBootstrapResponse:
    if settings.installer_enforced and not installation_service.is_installed(db):
        _check_code(db, request, x_install_code, "setup")
    result = installation_service.bootstrap(db, payload)
    mail = payload.mail
    if mail and mail.server_host:
        # Después de crear todo: guardar el correo reinicia los servicios.
        install_setup_service.save_mail(mail.server_host.strip(), int(mail.server_port or 587), (mail.username or "").strip(),
                                        mail.password or "", mail.use_tls, str(mail.sender_email))
    if settings.installer_enforced:
        install_code_service.consume()
    return result


@router.post("/recover-admin", response_model=InstallRecoverAdminResponse, summary="Crear o recuperar un administrador con el código de recuperación")
def recover_admin(payload: InstallRecoverAdminRequest, request: Request, db: Session = Depends(get_db),
                  x_install_code: str | None = Header(default=None)) -> InstallRecoverAdminResponse:
    if not installation_service.is_installed(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La recuperación solo está disponible con el sistema instalado.")
    _check_code(db, request, x_install_code, "recovery")
    problem = password_problem(payload.password)
    if problem:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=problem)
    from app.models.identity import User
    exists = db.query(User).filter(User.email == str(payload.email).lower()).first() is not None
    if not exists and (len(payload.full_name.strip()) < 3 or len(payload.document_id.strip()) < 5):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Para una cuenta nueva escribe el nombre completo y el número de documento.")
    try:
        result = create_or_recover(db, str(payload.email), payload.full_name.strip(), payload.document_id.strip() or None, payload.password, None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    install_code_service.consume()
    return InstallRecoverAdminResponse(**result)
