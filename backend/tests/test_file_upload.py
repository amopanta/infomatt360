import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import User


@pytest.fixture()
def upload_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    user = User(id="upload-user", full_name="Uploader", document_id="upload-doc", email="upload@example.com")
    with sessions() as db:
        db.add_all([
            UserProjectAssignment(user_id=user.id, project_id="upload-project", status="active"),
            BuilderTemplate(id="upload-template", project_id="upload-project", name="Upload template"),
        ])
        db.commit()

    monkeypatch.setattr(settings, "upload_directory", str(tmp_path))

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, tmp_path
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_upload_persists_content_and_metadata(upload_client):
    client, tmp_path = upload_client
    content = b"evidencia-infomatt360"
    response = client.post(
        "/api/v1/files/upload",
        data={"project_id": "upload-project", "asset_type": "FILE"},
        files={"upload": ("../informe.txt", content, "text/plain")},
    )

    assert response.status_code == 201
    asset = response.json()
    assert asset["original_name"] == "informe.txt"
    assert asset["size_bytes"] == len(content)
    assert asset["checksum"] == hashlib.sha256(content).hexdigest()
    stored = list((tmp_path / "upload-project").iterdir())
    assert len(stored) == 1
    assert stored[0].read_bytes() == content


def test_upload_denies_project_without_assignment(upload_client):
    client, _ = upload_client
    response = client.post(
        "/api/v1/files/upload",
        data={"project_id": "other-project", "asset_type": "IMAGE"},
        files={"upload": ("foto.jpg", b"image", "image/jpeg")},
    )
    assert response.status_code == 403


def test_saved_record_links_uploaded_asset(upload_client):
    client, _ = upload_client
    uploaded = client.post(
        "/api/v1/files/upload",
        data={"project_id": "upload-project", "asset_type": "IMAGE"},
        files={"upload": ("foto.jpg", b"image-content", "image/jpeg")},
    ).json()
    saved = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "upload-project",
            "template_id": "upload-template",
            "values": [{"field_name": "foto", "field_value_json": '{"file_asset_id":"' + uploaded["id"] + '"}'}],
        },
    )
    assert saved.status_code == 200
    files = client.get(f'/api/v1/files/project/upload-project?record_id={saved.json()["id"]}')
    assert [item["id"] for item in files.json()] == [uploaded["id"]]
