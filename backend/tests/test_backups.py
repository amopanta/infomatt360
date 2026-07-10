import shutil
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="backup-project", name="Backup Project")
        admin_role = Role(id="backup-admin-role", name="Admin Backup", permissions="backups.manage")
        basic_role = Role(id="backup-basic-role", name="Basico", permissions="records.read")
        admin = User(id="backup-admin", full_name="Admin", document_id="backup-admin-doc", email="backup-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="backup-basic", full_name="Basic", document_id="backup-basic-doc", email="backup-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            admin_role,
            basic_role,
            admin,
            basic,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_backup_run_copies_sqlite_file_and_lists_history():
    engine = setup_client()
    temp_dir = tempfile.mkdtemp(prefix="infomatt360-backup-test-")
    original_backup_directory = settings.backup_directory
    settings.backup_directory = temp_dir
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "backup-admin@example.com", "Admin12345!")
            basic_headers = auth(client, "backup-basic@example.com", "Basic12345!")

            denied = client.post("/api/v1/backups/run", headers=basic_headers, params={"project_id": "backup-project"})
            assert denied.status_code == 403

            created = client.post("/api/v1/backups/run", headers=admin_headers, params={"project_id": "backup-project"})
            assert created.status_code == 200
            body = created.json()
            assert body["status"] == "completed"
            assert body["file_path"] is not None
            assert body["size_bytes"] and body["size_bytes"] > 0
            assert Path(body["file_path"]).exists()

            listed = client.get("/api/v1/backups/project/backup-project", headers=admin_headers)
            assert listed.status_code == 200
            assert [row["id"] for row in listed.json()] == [body["id"]]
    finally:
        settings.backup_directory = original_backup_directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_backup_reports_failure_when_source_file_missing():
    engine = setup_client()
    temp_dir = tempfile.mkdtemp(prefix="infomatt360-backup-test-")
    original_backup_directory = settings.backup_directory
    original_database_url = settings.database_url
    settings.backup_directory = temp_dir
    settings.database_url = "sqlite:///./no-existe-para-la-prueba.db"
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "backup-admin@example.com", "Admin12345!")
            created = client.post("/api/v1/backups/run", headers=admin_headers, params={"project_id": "backup-project"})
            assert created.status_code == 200
            body = created.json()
            assert body["status"] == "failed"
            assert body["error"]
    finally:
        settings.backup_directory = original_backup_directory
        settings.database_url = original_database_url
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
