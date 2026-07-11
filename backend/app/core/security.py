from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_text(value: str) -> str:
    """Cifrado simetrico generico para secretos server-side (ej. tokens OAuth)."""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    return _fernet().decrypt(value.encode("ascii")).decode("utf-8")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_api_key_secret(secret: str) -> str:
    return hashlib.sha256(f"{settings.secret_key}:{secret}".encode("utf-8")).hexdigest()


def verify_api_key_secret(secret: str, secret_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key_secret(secret), secret_hash)


def create_access_token(
    subject: str,
    auth_version: int = 0,
    session_id: str | None = None,
    organization_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": subject, "ver": auth_version, "exp": expires_at}
    if session_id:
        payload["sid"] = session_id
    if organization_id:
        payload["org"] = organization_id
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_mfa_challenge_token(subject: str, auth_version: int) -> str:
    payload = {
        "sub": subject,
        "ver": auth_version,
        "type": "mfa_challenge",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
