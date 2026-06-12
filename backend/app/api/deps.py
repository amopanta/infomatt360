"""Dependencias comunes de API.

Aqui se definen dependencias reutilizables, como obtener el usuario autenticado
actual desde un token JWT. Esto evita repetir seguridad en cada endpoint.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.identity import User

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
        if user_id is None:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.status != "active":
        raise credentials_error
    return user
