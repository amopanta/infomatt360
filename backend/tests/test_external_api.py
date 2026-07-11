from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="ext-project", name="Proyecto Externo")
        other_project = Project(id="ext-other-project", name="Otro Proyecto")
        template = BuilderTemplate(id="ext-template", project_id=project.id, name="Formulario reportado", status="published")
        other_template = BuilderTemplate(id="ext-other-template", project_id=other_project.id, name="De otro proyecto", status="published")
        admin_role = Role(id="ext-admin-role", name="Admin", permissions="integrations.api_keys.manage")
        admin = User(id="ext-admin", full_name="Admin", document_id="ext-admin-doc", email="ext-admin@example.com", password_hash=hash_password("Admin12345!"))

        db.add_all([
            project, other_project, template, other_template, admin_role, admin,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            Participant(project_id=project.id, document_id="p-1", full_name="Beneficiario Uno"),
            RuntimeRecord(id="ext-record-approved", project_id=project.id, template_id=template.id, status="approved", submitted_by=admin.id),
            RuntimeRecord(id="ext-record-submitted", project_id=project.id, template_id=template.id, status="submitted", submitted_by=admin.id),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "ext-admin@example.com", "password": "Admin12345!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_api_key(client: TestClient, headers: dict[str, str], permissions: list[str], project_id: str = "ext-project") -> str:
    response = client.post(
        "/api/v1/api-keys/",
        headers=headers,
        json={"project_id": project_id, "name": "Partner key", "permissions": permissions},
    )
    assert response.status_code == 200
    return response.json()["api_key"]


def test_list_records_returns_only_approved_by_default_and_requires_permission():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)

            no_permission_key = create_api_key(client, headers, ["records.write"])
            denied = client.get(
                "/api/v1/external-api/records",
                params={"template_id": "ext-template"},
                headers={"X-API-Key": no_permission_key},
            )
            assert denied.status_code == 403

            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get(
                "/api/v1/external-api/records",
                params={"template_id": "ext-template"},
                headers={"X-API-Key": read_key},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["total"] == 1
            assert body["items"][0]["id"] == "ext-record-approved"

            all_statuses = client.get(
                "/api/v1/external-api/records",
                params={"template_id": "ext-template", "status": ""},
                headers={"X-API-Key": read_key},
            )
            assert all_statuses.status_code == 200
            assert all_statuses.json()["total"] == 2
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_records_rejects_template_from_another_project():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get(
                "/api/v1/external-api/records",
                params={"template_id": "ext-other-template"},
                headers={"X-API-Key": read_key},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_participants_requires_records_read():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get("/api/v1/external-api/participants", headers={"X-API-Key": read_key})
            assert response.status_code == 200
            assert len(response.json()) == 1
            assert response.json()[0]["full_name"] == "Beneficiario Uno"

            no_permission_key = create_api_key(client, headers, ["records.write"])
            response = client.get("/api/v1/external-api/participants", headers={"X-API-Key": no_permission_key})
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_summary_requires_reports_export_permission():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            denied = client.get("/api/v1/external-api/summary", headers={"X-API-Key": read_key})
            assert denied.status_code == 403

            reports_key = create_api_key(client, headers, ["reports.export"])
            response = client.get("/api/v1/external-api/summary", headers={"X-API-Key": reports_key})
            assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_endpoints_require_api_key():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/external-api/participants")
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
