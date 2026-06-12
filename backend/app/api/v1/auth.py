from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import auth_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesion")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.login(db, payload)
