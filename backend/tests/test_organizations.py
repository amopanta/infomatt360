from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

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
        project = Project(id="org-project", name="Proyecto Org")
        admin_role = Role(id="org-admin-role", name="Admin Org", permissions="organizations.manage,organizations.branding.manage")
        basic_role = Role(id="org-basic-role", name="Basico", permissions="records.read")
        admin = User(id="org-admin", full_name="Admin", document_id="org-admin-doc", email="org-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="org-basic", full_name="Basic", document_id="org-basic-doc", email="org-basic@example.com", password_hash=hash_password("Basic12345!"))
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


def test_organization_lifecycle_requires_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "org-admin@example.com", "Admin12345!")
            basic_headers = auth(client, "org-basic@example.com", "Basic12345!")

            denied = client.post("/api/v1/organizations/", headers=basic_headers, json={"name": "Fundacion X", "slug": "fundacion-x"})
            assert denied.status_code == 403

            created = client.post("/api/v1/organizations/", headers=admin_headers, json={"name": "Fundacion X", "slug": "fundacion-x"})
            assert created.status_code == 200
            organization_id = created.json()["id"]

            duplicate = client.post("/api/v1/organizations/", headers=admin_headers, json={"name": "Otra", "slug": "fundacion-x"})
            assert duplicate.status_code == 409

            listed = client.get("/api/v1/organizations/", headers=admin_headers)
            assert listed.status_code == 200
            assert any(row["id"] == organization_id for row in listed.json())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_public_branding_reflects_admin_configuration():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "org-admin@example.com", "Admin12345!")

            created = client.post("/api/v1/organizations/", headers=admin_headers, json={"name": "Fundacion X", "slug": "fundacion-x"})
            organization_id = created.json()["id"]

            missing_before = client.get("/api/v1/public/branding", params={"slug": "fundacion-x"})
            assert missing_before.status_code == 200
            assert missing_before.json()["logo_url"] is None

            updated = client.put(
                f"/api/v1/organizations/{organization_id}/branding",
                headers=admin_headers,
                json={"logo_url": "https://cdn.example.com/logo.png", "primary_color": "#0A2540", "slogan": "Territorio conectado"},
            )
            assert updated.status_code == 200
            assert updated.json()["primary_color"] == "#0A2540"

            public = client.get("/api/v1/public/branding", params={"slug": "fundacion-x"})
            assert public.status_code == 200
            body = public.json()
            assert body["organization_name"] == "Fundacion X"
            assert body["logo_url"] == "https://cdn.example.com/logo.png"
            assert body["slogan"] == "Territorio conectado"

            unknown = client.get("/api/v1/public/branding", params={"slug": "no-existe"})
            assert unknown.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
