import csv
import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.s3_storage_service as s3_module
from app.core.security import encrypt_text, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.files import FileAsset
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord
from app.models.storage import StorageProfile
from app.services.file_service import file_service


class FakeS3Client:
    def __init__(self, content: bytes = b"", fail: bool = False):
        self.content = content
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("boom")
        return {"Body": io.BytesIO(self.content)}


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    # tempfile.mkdtemp() en vez del fixture tmp_path de pytest: en esta
    # maquina Windows, backend/.pytest_cache queda bloqueado por un proceso
    # externo (ver memoria "pytest cache lock issue"), lo que rompe tmp_path.
    local_dir = Path(tempfile.mkdtemp(prefix="evi-download-test-"))

    def write_local(name: str, content: bytes) -> str:
        path = local_dir / name
        path.write_bytes(content)
        return str(path)

    with sessions() as db:
        project = Project(id="evi-project", name="Evidence Project")
        role = Role(id="evi-role", name="Miembro", permissions="records.read")
        member = User(id="evi-member", full_name="Member", document_id="evi-member-doc", email="evi-member@example.com", password_hash=hash_password("Member12345!"))
        outsider = User(id="evi-outsider", full_name="Outsider", document_id="evi-outsider-doc", email="evi-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        uploader = User(id="evi-uploader", full_name="Uploader Uno", document_id="evi-uploader-doc", email="evi-uploader@example.com", password_hash=hash_password("Uploader12345!"))

        template = BuilderTemplate(id="evi-template", project_id=project.id, name="Caracterizacion", status="published")

        participant_a = Participant(id="evi-participant-a", project_id=project.id, full_name="Ana Gómez")
        participant_b = Participant(id="evi-participant-b", project_id=project.id, full_name="Luis Pérez")

        record_approved = RuntimeRecord(id="evi-record-approved", project_id=project.id, template_id=template.id, status="approved")
        record_submitted = RuntimeRecord(id="evi-record-submitted", project_id=project.id, template_id=template.id, status="submitted")

        s3_profile = StorageProfile(
            id="evi-s3-profile",
            project_id=project.id,
            name="Boveda",
            provider="s3",
            bucket_name="evidencias",
            credentials_json=encrypt_text(json.dumps({"access_key_id": "AKIA", "secret_access_key": "shh", "region": "us-east-1"})),
            is_default="true",
            status="active",
        )

        db.add_all([
            project, role, member, outsider, uploader, template,
            participant_a, participant_b, record_approved, record_submitted, s3_profile,
            UserProjectAssignment(user_id=member.id, project_id=project.id, role_id=role.id, status="active"),
        ])

        assets = [
            FileAsset(
                id="evi-asset-a1", project_id=project.id, participant_id=participant_a.id, record_id=record_approved.id,
                asset_type="IMAGE", original_name="foto1.jpg", storage_provider="local",
                storage_path=write_local("a1.jpg", b"img-1"), mime_type="image/jpeg", size_bytes=5,
                created_by=uploader.id, created_at=datetime(2026, 7, 10),
            ),
            FileAsset(
                id="evi-asset-a2", project_id=project.id, participant_id=participant_a.id, record_id=record_submitted.id,
                asset_type="IMAGE", original_name="foto2.jpg", storage_provider="local",
                storage_path=write_local("a2.jpg", b"img-2"), mime_type="image/jpeg", size_bytes=5,
                created_by=uploader.id, created_at=datetime(2026, 7, 10),
            ),
            FileAsset(
                id="evi-asset-a3", project_id=project.id, participant_id=participant_b.id, record_id=None,
                asset_type="FILE", original_name="doc.txt", storage_provider="local",
                storage_path=write_local("a3.txt", b"doc-content"), mime_type="text/plain", size_bytes=11,
                created_by=member.id, created_at=datetime(2026, 7, 12),
            ),
            FileAsset(
                id="evi-asset-a4", project_id=project.id, participant_id=participant_b.id, record_id=record_submitted.id,
                asset_type="AUDIO", original_name="nota.mp3", storage_provider="local",
                storage_path=str(local_dir / "missing.mp3"), mime_type="audio/mpeg", size_bytes=999,
                created_by=uploader.id, created_at=datetime(2026, 7, 13),
            ),
            FileAsset(
                id="evi-asset-a5", project_id=project.id, participant_id=participant_b.id, record_id=record_approved.id,
                asset_type="VIDEO", original_name="clip.mp4", storage_provider="s3",
                storage_path="s3://evidencias/evi-project/clip.mp4", mime_type="video/mp4", size_bytes=20,
                created_by=member.id, created_at=datetime(2026, 7, 14),
            ),
        ]
        db.add_all(assets)
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions, local_dir


def teardown(engine, local_dir: Path) -> None:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(local_dir, ignore_errors=True)


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _manifest_rows(zip_bytes: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        with archive.open("manifest.csv") as handle:
            text = handle.read().decode("utf-8-sig")
    return list(csv.reader(text.splitlines()))


def test_filtered_asset_ids_by_participant_template_status_gestor_and_date():
    engine, sessions, local_dir = setup_client()
    try:
        with sessions() as db:
            assert set(file_service.list_filtered_asset_ids(db, "evi-project", participant_id="evi-participant-a")) == {"evi-asset-a1", "evi-asset-a2"}
            assert set(file_service.list_filtered_asset_ids(db, "evi-project", template_id="evi-template", status="approved")) == {"evi-asset-a1", "evi-asset-a5"}
            assert set(file_service.list_filtered_asset_ids(db, "evi-project", created_by="evi-uploader")) == {"evi-asset-a1", "evi-asset-a2", "evi-asset-a4"}
            assert set(file_service.list_filtered_asset_ids(db, "evi-project", date_from=datetime(2026, 7, 12), date_to=datetime(2026, 7, 13, 23, 59, 59))) == {"evi-asset-a3", "evi-asset-a4"}
            # El archivo sin record_id (a3) queda excluido por filtros de formulario/estado (join semantics).
            assert "evi-asset-a3" not in file_service.list_filtered_asset_ids(db, "evi-project", template_id="evi-template")
    finally:
        teardown(engine, local_dir)


def test_download_batch_permission_denied_for_outsider():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "evi-outsider@example.com", "Outsider12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1"]}, headers=outsider_headers)
            assert response.status_code == 403
    finally:
        teardown(engine, local_dir)


def test_download_batch_explicit_ids_take_priority_over_filters():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post(
                "/api/v1/files/project/evi-project/download-batch",
                json={"asset_ids": ["evi-asset-a3"], "participant_id": "evi-participant-a"},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = set(archive.namelist())
            assert "manifest.csv" in names
            assert len(names) == 2
            assert any(name.startswith("Luis-Perez_FILE_2026-07-12") for name in names)
    finally:
        teardown(engine, local_dir)


def test_download_batch_builds_zip_with_renamed_files_and_manifest():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1"]}, headers=headers)
            assert response.status_code == 200, response.text
            assert response.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert "Ana-Gomez_IMAGE_2026-07-10.jpg" in archive.namelist()
                assert archive.read("Ana-Gomez_IMAGE_2026-07-10.jpg") == b"img-1"
            rows = _manifest_rows(response.content)
            assert rows[0] == ["file_id", "status", "error"]
            assert ["evi-asset-a1", "success", ""] in rows
    finally:
        teardown(engine, local_dir)


def test_download_batch_renaming_collision_appends_disambiguator():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1", "evi-asset-a2"]}, headers=headers)
            assert response.status_code == 200, response.text
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = set(archive.namelist())
            assert "Ana-Gomez_IMAGE_2026-07-10.jpg" in names
            assert "Ana-Gomez_IMAGE_2026-07-10_2.jpg" in names
    finally:
        teardown(engine, local_dir)


def test_download_batch_count_cap_returns_422(monkeypatch):
    from app.core.config import settings

    engine, _sessions, local_dir = setup_client()
    monkeypatch.setattr(settings, "evidence_batch_max_records", 1)
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1", "evi-asset-a2"]}, headers=headers)
            assert response.status_code == 422
            assert "1 archivos" in response.json()["detail"]
    finally:
        teardown(engine, local_dir)


def test_download_batch_size_cap_returns_422(monkeypatch):
    from app.core.config import settings

    engine, _sessions, local_dir = setup_client()
    monkeypatch.setattr(settings, "evidence_batch_max_total_size_mb", 0)
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1", "evi-asset-a2"]}, headers=headers)
            assert response.status_code == 422
            assert "MB" in response.json()["detail"]
    finally:
        teardown(engine, local_dir)


def test_download_batch_missing_local_file_marks_failed_without_aborting():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a1", "evi-asset-a4"]}, headers=headers)
            assert response.status_code == 200, response.text
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = archive.namelist()
            assert any(name.startswith("Ana-Gomez_IMAGE") for name in names)
            rows = _manifest_rows(response.content)
            failed_rows = [row for row in rows if row[0] == "evi-asset-a4"]
            assert failed_rows and failed_rows[0][1] == "failed"
    finally:
        teardown(engine, local_dir)


def test_download_single_file_local():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.get("/api/v1/files/evi-asset-a1/download", headers=headers)
            assert response.status_code == 200
            assert response.content == b"img-1"
            assert "foto1.jpg" in response.headers["content-disposition"]
    finally:
        teardown(engine, local_dir)


def test_download_batch_s3_asset_via_mocked_boto3(monkeypatch):
    engine, _sessions, local_dir = setup_client()
    fake_client = FakeS3Client(content=b"video-bytes")
    monkeypatch.setattr(s3_module.boto3, "client", lambda *args, **kwargs: fake_client)
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a5"]}, headers=headers)
            assert response.status_code == 200, response.text
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = archive.namelist()
                matched = [name for name in names if name.startswith("Luis-Perez_VIDEO")]
                assert matched
                assert archive.read(matched[0]) == b"video-bytes"
    finally:
        teardown(engine, local_dir)


def test_download_batch_s3_get_object_failure_marks_failed(monkeypatch):
    engine, _sessions, local_dir = setup_client()
    fake_client = FakeS3Client(fail=True)
    monkeypatch.setattr(s3_module.boto3, "client", lambda *args, **kwargs: fake_client)
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.post("/api/v1/files/project/evi-project/download-batch", json={"asset_ids": ["evi-asset-a5"]}, headers=headers)
            assert response.status_code == 200, response.text
            rows = _manifest_rows(response.content)
            failed_rows = [row for row in rows if row[0] == "evi-asset-a5"]
            assert failed_rows and failed_rows[0][1] == "failed"
    finally:
        teardown(engine, local_dir)


def test_list_uploaders_scoped_to_project_and_requires_access():
    engine, _sessions, local_dir = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "evi-member@example.com", "Member12345!")
            response = client.get("/api/v1/files/project/evi-project/uploaders", headers=headers)
            assert response.status_code == 200, response.text
            names = {row["full_name"] for row in response.json()}
            assert names == {"Member", "Uploader Uno"}

            outsider_headers = auth(client, "evi-outsider@example.com", "Outsider12345!")
            denied = client.get("/api/v1/files/project/evi-project/uploaders", headers=outsider_headers)
            assert denied.status_code == 403
    finally:
        teardown(engine, local_dir)
