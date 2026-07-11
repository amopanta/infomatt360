import time

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.identity import User
from app.services.mfa_service import mfa_service


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(
            id="field-user",
            full_name="Gestor de Campo",
            document_id="field-user-doc",
            email="field-user@example.com",
            password_hash=hash_password("FieldUser12345!"),
            locked_device_fingerprint="tablet-serial-001",
        )
        db.add(user)
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def _expiry_seconds(access_token: str) -> float:
    payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    return payload["exp"]


def test_login_without_device_fingerprint_uses_default_expiry():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/login", json={"email": "field-user@example.com", "password": "FieldUser12345!"})
            assert response.status_code == 200
            exp = _expiry_seconds(response.json()["access_token"])
            # No debe acercarse a la ventana extendida (10h); el default es 60 min.
            assert exp - time.time() < settings.access_token_expire_minutes_field_device * 60 / 2
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_login_with_mismatched_device_fingerprint_uses_default_expiry():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "field-user@example.com", "password": "FieldUser12345!", "device_fingerprint": "some-other-device"},
            )
            assert response.status_code == 200
            exp = _expiry_seconds(response.json()["access_token"])
            import time
            assert exp - time.time() < settings.access_token_expire_minutes_field_device * 60 / 2
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_login_with_matching_locked_device_grants_extended_session():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "field-user@example.com", "password": "FieldUser12345!", "device_fingerprint": "tablet-serial-001"},
            )
            assert response.status_code == 200
            exp = _expiry_seconds(response.json()["access_token"])
            import time
            remaining_minutes = (exp - time.time()) / 60
            assert remaining_minutes > settings.access_token_expire_minutes
            assert remaining_minutes <= settings.access_token_expire_minutes_field_device + 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_mfa_login_with_matching_locked_device_grants_extended_session():
    engine, sessions = setup_client()
    secret = mfa_service.new_secret()
    with sessions() as db:
        user = db.query(User).filter(User.id == "field-user").one()
        user.mfa_enabled = True
        user.mfa_secret_encrypted = mfa_service.encrypt_secret(secret)
        db.commit()
    try:
        with TestClient(app) as client:
            challenge = client.post("/api/v1/auth/login", json={"email": "field-user@example.com", "password": "FieldUser12345!"})
            assert challenge.status_code == 200
            assert challenge.json()["mfa_required"] is True
            code = mfa_service._totp(secret, int(time.time()) // 30)
            verified = client.post(
                "/api/v1/auth/mfa/verify",
                json={
                    "challenge_token": challenge.json()["mfa_challenge_token"],
                    "code": code,
                    "device_fingerprint": "tablet-serial-001",
                },
            )
            assert verified.status_code == 200
            exp = _expiry_seconds(verified.json()["access_token"])
            remaining_minutes = (exp - time.time()) / 60
            assert remaining_minutes > settings.access_token_expire_minutes
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
