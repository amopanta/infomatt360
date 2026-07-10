import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.gdrive_storage_service as gdrive_module
from app.core.config import settings
from app.core.security import decrypt_text, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, User
from app.models.storage import StorageProfile


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="gdrive-project", name="GDrive Project")
        member = User(id="gdrive-member", full_name="Member", document_id="gdrive-member-doc", email="gdrive-member@example.com", password_hash=hash_password("Member12345!"))
        outsider = User(id="gdrive-outsider", full_name="Outsider", document_id="gdrive-outsider-doc", email="gdrive-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        db.add_all([
            project,
            member,
            outsider,
            UserProjectAssignment(user_id=member.id, project_id=project.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _enable_gdrive_config():
    originals = (settings.google_oauth_client_id, settings.google_oauth_client_secret, settings.google_oauth_redirect_uri)
    settings.google_oauth_client_id = "client-123"
    settings.google_oauth_client_secret = "secret-456"
    settings.google_oauth_redirect_uri = "https://app.example.com/oauth/gdrive/callback"
    return originals


def _restore_gdrive_config(originals):
    settings.google_oauth_client_id, settings.google_oauth_client_secret, settings.google_oauth_redirect_uri = originals


def test_authorize_rejects_when_not_configured_and_requires_project_access():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            member_headers = auth(client, "gdrive-member@example.com", "Member12345!")
            outsider_headers = auth(client, "gdrive-outsider@example.com", "Outsider12345!")

            not_configured = client.get("/api/v1/storage/oauth/gdrive/authorize", headers=member_headers, params={"project_id": "gdrive-project"})
            assert not_configured.status_code == 400

            originals = _enable_gdrive_config()
            try:
                denied = client.get("/api/v1/storage/oauth/gdrive/authorize", headers=outsider_headers, params={"project_id": "gdrive-project"})
                assert denied.status_code == 403

                allowed = client.get("/api/v1/storage/oauth/gdrive/authorize", headers=member_headers, params={"project_id": "gdrive-project"})
                assert allowed.status_code == 200
                parsed = urlparse(allowed.json()["authorization_url"])
                query = parse_qs(parsed.query)
                assert query["client_id"] == ["client-123"]
                assert query["redirect_uri"] == ["https://app.example.com/oauth/gdrive/callback"]
                assert query["state"][0].startswith("gdrive-project:")
            finally:
                _restore_gdrive_config(originals)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_callback_rejects_tampered_state():
    engine, _sessions = setup_client()
    originals = _enable_gdrive_config()
    try:
        with TestClient(app) as client:
            tampered = client.get("/api/v1/storage/oauth/gdrive/callback", params={"code": "abc", "state": "gdrive-project:not-a-valid-signature"})
            assert tampered.status_code == 400
    finally:
        _restore_gdrive_config(originals)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_callback_exchanges_code_and_stores_encrypted_tokens(monkeypatch):
    engine, sessions = setup_client()
    originals = _enable_gdrive_config()

    def fake_post(url, **kwargs):
        assert url == gdrive_module.TOKEN_URL
        assert kwargs["data"]["code"] == "auth-code-xyz"
        return FakeResponse(200, {"access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3600})

    monkeypatch.setattr(gdrive_module.httpx, "post", fake_post)
    try:
        with TestClient(app) as client:
            state = gdrive_module.gdrive_storage_service.sign_state("gdrive-project")
            response = client.get("/api/v1/storage/oauth/gdrive/callback", params={"code": "auth-code-xyz", "state": state})
            assert response.status_code == 200
            body = response.json()
            assert body["provider"] == "gdrive"
            assert body["project_id"] == "gdrive-project"
            assert "oauth_tokens_encrypted" not in body

            with sessions() as db:
                profile = db.query(StorageProfile).filter(StorageProfile.project_id == "gdrive-project", StorageProfile.provider == "gdrive").one()
                stored = json.loads(decrypt_text(profile.oauth_tokens_encrypted))
                assert stored["access_token"] == "access-1"
                assert stored["refresh_token"] == "refresh-1"
    finally:
        _restore_gdrive_config(originals)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_upload_file_refreshes_expired_access_token(monkeypatch):
    engine, sessions = setup_client()
    originals = _enable_gdrive_config()
    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url == gdrive_module.TOKEN_URL:
            assert kwargs["data"]["grant_type"] == "refresh_token"
            assert kwargs["data"]["refresh_token"] == "refresh-expired"
            return FakeResponse(200, {"access_token": "access-refreshed", "expires_in": 3600})
        if url == gdrive_module.UPLOAD_URL:
            assert kwargs["headers"]["Authorization"] == "Bearer access-refreshed"
            return FakeResponse(200, {"id": "drive-file-id-1"})
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(gdrive_module.httpx, "post", fake_post)
    try:
        with sessions() as db:
            expired_tokens = {"access_token": "access-old", "refresh_token": "refresh-expired", "expires_at": time.time() - 10}
            from app.core.security import encrypt_text

            profile = StorageProfile(project_id="gdrive-project", name="Google Drive", provider="gdrive", oauth_tokens_encrypted=encrypt_text(json.dumps(expired_tokens)))
            db.add(profile)
            db.commit()
            db.refresh(profile)

            result = gdrive_module.gdrive_storage_service.upload_file(db, profile, "evidencia.jpg", b"contenido", "image/jpeg")
            assert result == {"id": "drive-file-id-1"}
            assert calls == [gdrive_module.TOKEN_URL, gdrive_module.UPLOAD_URL]
    finally:
        _restore_gdrive_config(originals)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
