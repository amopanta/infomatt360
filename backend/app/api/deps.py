"""Dependencias comunes de API.

Aqui se definen dependencias reutilizables, como obtener el usuario autenticado
actual desde un token JWT. Esto evita repetir seguridad en cada endpoint.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.db.session import get_db
from app.models.identity import RefreshToken, User

# La URL apunta al endpoint real de login. FastAPI la usa en Swagger/OpenAPI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Obtiene el usuario autenticado a partir del token JWT.

    Si el token es invalido, vencido o el usuario ya no existe, se rechaza
    la solicitud con 401.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        auth_version = payload.get("ver", 0)
        session_id = payload.get("sid")
        organization_id = payload.get("org")
        if user_id is None:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.status != "active" or user.auth_version != auth_version:
        raise credentials_error
    # Contexto de organizacion activa, no persistido; solo disponible durante el request.
    user.active_organization_id = organization_id
    if session_id:
        active_session = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.family_id == session_id,
            RefreshToken.auth_version == user.auth_version,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utc_now(),
        ).first()
        if active_session is None:
            raise credentials_error
    return user
