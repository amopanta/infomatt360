from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.api_key import ProjectApiKey
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="api-project", name="API Project")
        admin_role = Role(id="api-admin-role", name="Admin API", permissions="integrations.api_keys.manage")
        basic_role = Role(id="api-basic-role", name="Basico", permissions="records.read")
        admin = User(id="api-admin", full_name="Admin", document_id="api-admin-doc", email="api-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="api-basic", full_name="Basic", document_id="api-basic-doc", email="api-basic@example.com", password_hash=hash_password("Basic12345!"))
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
    return engine, sessions


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_api_key_lifecycle_and_x_api_key_authentication():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "api-admin@example.com", "Admin12345!")
            basic_headers = auth(client, "api-basic@example.com", "Basic12345!")

            denied = client.post(
                "/api/v1/api-keys/",
                headers=basic_headers,
                json={"project_id": "api-project", "name": "Denied", "permissions": ["records.read"]},
            )
            assert denied.status_code == 403

            created = client.post(
                "/api/v1/api-keys/",
                headers=admin_headers,
                json={"project_id": "api-project", "name": "Integracion externa", "permissions": ["records.read", "reports.export"], "rate_limit_profile": "high_volume"},
            )
            assert created.status_code == 200
            created_data = created.json()
            assert created_data["api_key"].startswith("im360_")
            assert created_data["permissions"] == ["records.read", "reports.export"]
            assert created_data["rate_limit_profile"] == "high_volume"

            listed = client.get("/api/v1/api-keys/api-project", headers=admin_headers)
            assert listed.status_code == 200
            assert "api_key" not in listed.json()[0]
            assert listed.json()[0]["key_id"] == created_data["key_id"]
            assert listed.json()[0]["rate_limit_profile"] == "high_volume"

            check = client.get("/api/v1/api-keys/auth/check", headers={"X-API-Key": created_data["api_key"]})
            assert check.status_code == 200
            assert check.json()["project_id"] == "api-project"
            assert check.json()["permissions"] == ["records.read", "reports.export"]

            with sessions() as db:
                row = db.query(ProjectApiKey).filter(ProjectApiKey.key_id == created_data["key_id"]).one()
                assert row.secret_hash
                assert created_data["api_key"] not in row.secret_hash
                assert row.last_used_at is not None

            revoked = client.delete(f"/api/v1/api-keys/api-project/{created_data['key_id']}", headers=admin_headers)
            assert revoked.status_code == 200
            assert revoked.json()["status"] == "revoked"

            rejected = client.get("/api/v1/api-keys/auth/check", headers={"X-API-Key": created_data["api_key"]})
            assert rejected.status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_malformed_or_missing_api_key_is_rejected():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            missing = client.get("/api/v1/api-keys/auth/check")
            malformed = client.get("/api/v1/api-keys/auth/check", headers={"X-API-Key": "bad-key"})
            assert missing.status_code == 401
            assert malformed.status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
