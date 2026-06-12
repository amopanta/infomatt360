"""Endpoints de seguridad y sesion actual."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.identity import User
from app.schemas.security import CurrentUserResponse

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse, summary="Consultar usuario autenticado")
def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Devuelve informacion basica del usuario autenticado.

    Este endpoint sirve para que web, Android y escritorio validen sesion,
    perfil y canales disponibles.
    """
    return CurrentUserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        status=current_user.status,
        allowed_channels=current_user.allowed_channels.split(",") if current_user.allowed_channels else [],
    )
