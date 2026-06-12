from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.identity_service import identity_service


class AuthService:
    def login(self, db: Session, payload: LoginRequest) -> TokenResponse:
        user = identity_service.get_user_by_email(db, str(payload.email))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no activo")
        return TokenResponse(access_token=create_access_token(user.id))


auth_service = AuthService()
