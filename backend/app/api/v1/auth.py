from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.identity import User
from app.schemas.auth import ForgotPasswordRequest, ForgotPasswordResponse, LoginRequest, LoginResponse, MfaCodeRequest, MfaConfirmResponse, MfaDisableRequest, MfaSetupRequest, MfaSetupResponse, MfaStatusResponse, MfaVerifyRequest, PasswordChangeRequest, PasswordOperationResponse, PasswordResetRequest, RefreshRequest, SessionResponse, TokenResponse
from app.services.auth_service import auth_service
from app.services.auth_throttle_service import auth_throttle_service
from app.services.password_mail_service import password_mail_service

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_production() -> bool:
    return settings.environment.lower().strip() in {"production", "prod"}


def _allowed_web_origins() -> set[str]:
    origins = {origin.strip().rstrip("/") for origin in settings.cors_allowed_origins.split(",") if origin.strip()}
    if settings.frontend_url:
        origins.add(settings.frontend_url.strip().rstrip("/"))
    return origins


def _request_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if not referer:
        return ""
    return "/".join(referer.split("/", 3)[:3]).rstrip("/")


def _validate_cookie_refresh_origin(request: Request) -> None:
    if not _is_production():
        return
    origin = _request_origin(request)
    if not origin or origin not in _allowed_web_origins():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origen no permitido para refresh con cookie")


def _set_refresh_cookie(response: Response, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


@router.post("/login", response_model=LoginResponse, summary="Iniciar sesion")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    ip_address = _client_ip(request)
    email_key = f"{payload.email}|{ip_address}"
    if auth_throttle_service.is_blocked(db, "login-email-ip", email_key) or auth_throttle_service.is_blocked(db, "login-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        login_response = auth_service.login(db, payload)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            email_allowed = auth_throttle_service.record_attempt(db, "login-email-ip", email_key, maximum=5, window_minutes=15, block_minutes=15)
            ip_allowed = auth_throttle_service.record_attempt(db, "login-ip", ip_address, maximum=25, window_minutes=15, block_minutes=15)
            if not email_allowed or not ip_allowed:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise
    auth_throttle_service.clear(db, "login-email-ip", email_key)
    _set_refresh_cookie(response, login_response.refresh_token)
    login_response.refresh_token = None
    return login_response


@router.post("/mfa/verify", response_model=TokenResponse, summary="Completar inicio con MFA")
def verify_mfa(payload: MfaVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "mfa-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        challenge = jwt.decode(payload.challenge_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if challenge.get("type") != "mfa_challenge":
            raise JWTError("tipo invalido")
        user = db.query(User).filter(
            User.id == challenge.get("sub"),
            User.status == "active",
            User.auth_version == challenge.get("ver"),
            User.mfa_enabled.is_(True),
        ).first()
        if user is None:
            raise JWTError("usuario invalido")
        token_response = auth_service.complete_mfa_login(db, user, payload.code)
        _set_refresh_cookie(response, token_response.refresh_token)
        token_response.refresh_token = None
        return token_response
    except (JWTError, HTTPException) as exc:
        allowed = auth_throttle_service.record_attempt(db, "mfa-ip", ip_address, maximum=10, window_minutes=15, block_minutes=15)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo o desafio MFA invalido") from exc


@router.get("/mfa/status", response_model=MfaStatusResponse)
def mfa_status(current_user: User = Depends(get_current_user)) -> MfaStatusResponse:
    return auth_service.mfa_status(current_user)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def setup_mfa(payload: MfaSetupRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MfaSetupResponse:
    return auth_service.setup_mfa(db, current_user, payload)


@router.post("/mfa/confirm", response_model=MfaConfirmResponse)
def confirm_mfa(payload: MfaCodeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> MfaConfirmResponse:
    return auth_service.confirm_mfa(db, current_user, payload.code)


@router.post("/mfa/disable", response_model=PasswordOperationResponse)
def disable_mfa(payload: MfaDisableRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PasswordOperationResponse:
    auth_service.disable_mfa(db, current_user, payload)
    return PasswordOperationResponse(message="MFA desactivado. Inicia sesion nuevamente.")


@router.get("/session", response_model=SessionResponse, summary="Consultar sesion actual")
def current_session(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SessionResponse:
    return auth_service.get_session(db, current_user)


@router.post("/refresh", response_model=TokenResponse, summary="Rotar refresh token")
def refresh_token(payload: RefreshRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "refresh-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        cookie_refresh_token = request.cookies.get(settings.refresh_cookie_name)
        if not payload.refresh_token and cookie_refresh_token:
            _validate_cookie_refresh_origin(request)
        refresh_payload = RefreshRequest(refresh_token=payload.refresh_token or cookie_refresh_token)
        token_response = auth_service.refresh(db, refresh_payload)
        _set_refresh_cookie(response, token_response.refresh_token)
        token_response.refresh_token = None
        return token_response
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            allowed = auth_throttle_service.record_attempt(db, "refresh-ip", ip_address, maximum=10, window_minutes=15, block_minutes=15)
            if not allowed:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise


@router.post("/logout", response_model=PasswordOperationResponse, summary="Cerrar todas las sesiones")
def logout(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PasswordOperationResponse:
    auth_service.logout(db, current_user)
    _clear_refresh_cookie(response)
    return PasswordOperationResponse(message="Sesion cerrada en todos los dispositivos.")


@router.post("/password/change", response_model=PasswordOperationResponse)
def change_password(payload: PasswordChangeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PasswordOperationResponse:
    auth_service.change_password(db, current_user, payload)
    return PasswordOperationResponse(message="Contraseña actualizada. Inicia sesión nuevamente.")


@router.post("/password/forgot", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    # La respuesta nunca revela si existe la cuenta ni si el proveedor pudo entregar el mensaje.
    ip_address = _client_ip(request)
    email_allowed = auth_throttle_service.record_attempt(db, "forgot-email-ip", f"{payload.email}|{ip_address}", maximum=3, window_minutes=60, block_minutes=60)
    ip_allowed = auth_throttle_service.record_attempt(db, "forgot-ip", ip_address, maximum=20, window_minutes=60, block_minutes=60)
    raw_token = auth_service.issue_reset_token(db, str(payload.email)) if email_allowed and ip_allowed else None
    if raw_token:
        password_mail_service.send_reset_link(str(payload.email), raw_token)
    return ForgotPasswordResponse()


@router.post("/password/reset", response_model=PasswordOperationResponse)
def reset_password(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)) -> PasswordOperationResponse:
    ip_address = _client_ip(request)
    if auth_throttle_service.is_blocked(db, "reset-ip", ip_address):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde")
    try:
        auth_service.reset_password(db, payload)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            allowed = auth_throttle_service.record_attempt(db, "reset-ip", ip_address, maximum=10, window_minutes=15, block_minutes=15)
            if not allowed:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Intenta nuevamente mas tarde") from exc
        raise
    return PasswordOperationResponse(message="Contraseña restablecida. Ya puedes iniciar sesión.")
