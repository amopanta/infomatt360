import hashlib
import io
import json

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.s3_storage_service as s3_module
from app.core.security import decrypt_text, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Role, User
from app.models.storage import StorageProfile


class FakeS3Client:
    def __init__(self, fail: bool = False):
        self.calls: list[dict[str, object]] = []
        self.fail = fail

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(kwargs)
        return {"ETag": "\"fake-etag\""}


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def s3_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        storage_role = Role(id="s3-storage-role", name="Almacenamiento", permissions="storage.manage")
        low_priv_role = Role(id="s3-low-priv-role", name="Solo campo", permissions="records.write")
        member = User(id="s3-member", full_name="Member", document_id="s3-member-doc", email="s3-member@example.com", password_hash=hash_password("Member12345!"))
        outsider = User(id="s3-outsider", full_name="Outsider", document_id="s3-outsider-doc", email="s3-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        low_priv = User(id="s3-low-priv", full_name="Gestor de campo", document_id="s3-low-priv-doc", email="s3-low-priv@example.com", password_hash=hash_password("LowPriv12345!"))
        db.add_all([
            storage_role,
            low_priv_role,
            member,
            outsider,
            low_priv,
            UserProjectAssignment(user_id=member.id, project_id="s3-project", role_id=storage_role.id, status="active"),
            UserProjectAssignment(user_id=low_priv.id, project_id="s3-project", role_id=low_priv_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_connect_requires_project_access_and_hides_secrets(s3_client):
    client, sessions = s3_client
    outsider_headers = auth(client, "s3-outsider@example.com", "Outsider12345!")
    member_headers = auth(client, "s3-member@example.com", "Member12345!")

    denied = client.post(
        "/api/v1/storage/s3/connect",
        json={"project_id": "s3-project", "bucket_name": "evidencias", "access_key_id": "AKIA", "secret_access_key": "shh"},
        headers=outsider_headers,
    )
    assert denied.status_code == 403

    low_priv_headers = auth(client, "s3-low-priv@example.com", "LowPriv12345!")
    denied_low_priv = client.post(
        "/api/v1/storage/s3/connect",
        json={"project_id": "s3-project", "bucket_name": "evidencias", "access_key_id": "AKIA", "secret_access_key": "shh"},
        headers=low_priv_headers,
    )
    assert denied_low_priv.status_code == 403

    response = client.post(
        "/api/v1/storage/s3/connect",
        json={"project_id": "s3-project", "bucket_name": "evidencias", "access_key_id": "AKIA", "secret_access_key": "shh"},
        headers=member_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "s3"
    assert body["bucket_name"] == "evidencias"
    assert "credentials_json" not in body
    assert "access_key_id" not in body
    assert "secret_access_key" not in body

    with sessions() as db:
        profile = db.query(StorageProfile).filter(StorageProfile.project_id == "s3-project", StorageProfile.provider == "s3").one()
        stored = json.loads(decrypt_text(profile.credentials_json))
        assert stored["access_key_id"] == "AKIA"
        assert stored["secret_access_key"] == "shh"


def test_upload_routes_to_s3_and_converts_image_to_webp(s3_client, monkeypatch):
    client, sessions = s3_client
    member_headers = auth(client, "s3-member@example.com", "Member12345!")
    client.post(
        "/api/v1/storage/s3/connect",
        json={"project_id": "s3-project", "bucket_name": "evidencias", "access_key_id": "AKIA", "secret_access_key": "shh", "endpoint_url": "https://minio.local"},
        headers=member_headers,
    )

    fake_client = FakeS3Client()
    monkeypatch.setattr(s3_module.boto3, "client", lambda *args, **kwargs: fake_client)

    content = _png_bytes()
    response = client.post(
        "/api/v1/files/upload",
        data={"project_id": "s3-project", "asset_type": "IMAGE"},
        files={"upload": ("foto.png", content, "image/png")},
        headers=member_headers,
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["storage_provider"] == "s3"
    assert asset["storage_path"].startswith("s3://evidencias/s3-project/")
    assert asset["mime_type"] == "image/webp"
    assert asset["original_name"] == "foto.webp"

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["Bucket"] == "evidencias"
    assert call["ContentType"] == "image/webp"
    assert hashlib.sha256(call["Body"]).hexdigest() == asset["checksum"]
    assert call["Body"] != content


def test_upload_falls_back_to_local_without_s3_profile(s3_client):
    client, _sessions = s3_client
    member_headers = auth(client, "s3-member@example.com", "Member12345!")
    response = client.post(
        "/api/v1/files/upload",
        data={"project_id": "s3-project", "asset_type": "FILE"},
        files={"upload": ("informe.txt", b"contenido", "text/plain")},
        headers=member_headers,
    )
    assert response.status_code == 201
    assert response.json()["storage_provider"] == "local"


def test_upload_surfaces_s3_failure_as_bad_gateway(s3_client, monkeypatch):
    client, _sessions = s3_client
    member_headers = auth(client, "s3-member@example.com", "Member12345!")
    client.post(
        "/api/v1/storage/s3/connect",
        json={"project_id": "s3-project", "bucket_name": "evidencias", "access_key_id": "AKIA", "secret_access_key": "shh"},
        headers=member_headers,
    )
    monkeypatch.setattr(s3_module.boto3, "client", lambda *args, **kwargs: FakeS3Client(fail=True))

    response = client.post(
        "/api/v1/files/upload",
        data={"project_id": "s3-project", "asset_type": "FILE"},
        files={"upload": ("informe.txt", b"contenido", "text/plain")},
        headers=member_headers,
    )
    assert response.status_code == 502
