import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

UPDATED_AT_OLD = datetime(2026, 7, 10, 8, 0, 0)
UPDATED_AT_NEW = datetime(2026, 7, 15, 8, 0, 0)


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
            BuilderComponent(template_id=template.id, component_type="DOCUMENT_ID", name="cedula", label="Cedula", sort_order=1),
            BuilderComponent(template_id=template.id, component_type="TEXT", name="nombre", label="Nombre", sort_order=2),
            RuntimeRecord(id="ext-record-approved", project_id=project.id, template_id=template.id, status="approved", submitted_by=admin.id, updated_at=UPDATED_AT_OLD),
            RuntimeRecord(id="ext-record-submitted", project_id=project.id, template_id=template.id, status="submitted", submitted_by=admin.id, updated_at=UPDATED_AT_NEW),
            RuntimeRecordValue(record_id="ext-record-approved", field_name="cedula", field_value_json=json.dumps("123456")),
            RuntimeRecordValue(record_id="ext-record-approved", field_name="nombre", field_value_json=json.dumps("=cmd|/c calc!A1")),
            RuntimeRecordValue(record_id="ext-record-submitted", field_name="cedula", field_value_json=json.dumps("789012")),
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
            assert client.get("/api/v1/external-api/records/tabular", params={"template_id": "ext-template"}).status_code == 401
            assert client.get("/api/v1/external-api/templates").status_code == 401
            assert client.get("/api/v1/external-api/templates/ext-template/schema").status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_tabular_records_has_stable_columns_across_filtered_calls():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])

            approved_only = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template"},
                headers={"X-API-Key": read_key},
            )
            all_statuses = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template", "status": ""},
                headers={"X-API-Key": read_key},
            )
            assert approved_only.status_code == 200, approved_only.text
            assert all_statuses.status_code == 200, all_statuses.text
            assert approved_only.json()["columns"] == ["cedula", "nombre"]
            assert all_statuses.json()["columns"] == ["cedula", "nombre"]

            submitted_row = next(item for item in all_statuses.json()["items"] if item["record_id"] == "ext-record-submitted")
            assert submitted_row["fields"]["cedula"] == "789012"
            assert submitted_row["fields"]["nombre"] is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_tabular_records_updated_since_filters_incrementally_and_inclusively():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])

            between = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template", "status": "", "updated_since": "2026-07-12T00:00:00"},
                headers={"X-API-Key": read_key},
            )
            assert between.status_code == 200, between.text
            assert {item["record_id"] for item in between.json()["items"]} == {"ext-record-submitted"}

            inclusive_boundary = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template", "status": "", "updated_since": UPDATED_AT_NEW.isoformat()},
                headers={"X-API-Key": read_key},
            )
            assert inclusive_boundary.status_code == 200
            assert {item["record_id"] for item in inclusive_boundary.json()["items"]} == {"ext-record-submitted"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_tabular_records_updated_since_accepts_timezone_aware_query_param():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template", "status": "", "updated_since": "2026-07-12T00:00:00Z"},
                headers={"X-API-Key": read_key},
            )
            assert response.status_code == 200, response.text
            assert {item["record_id"] for item in response.json()["items"]} == {"ext-record-submitted"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_tabular_records_escapes_formula_like_values():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-template"},
                headers={"X-API-Key": read_key},
            )
            assert response.status_code == 200, response.text
            row = response.json()["items"][0]
            assert row["fields"]["nombre"] == "'=cmd|/c calc!A1"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_tabular_records_rejects_template_from_another_project():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get(
                "/api/v1/external-api/records/tabular",
                params={"template_id": "ext-other-template"},
                headers={"X-API-Key": read_key},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_external_templates_returns_only_project_templates_and_requires_permission():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get("/api/v1/external-api/templates", headers={"X-API-Key": read_key})
            assert response.status_code == 200, response.text
            ids = {item["id"] for item in response.json()}
            assert ids == {"ext-template"}

            no_permission_key = create_api_key(client, headers, ["records.write"])
            denied = client.get("/api/v1/external-api/templates", headers={"X-API-Key": no_permission_key})
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_get_external_template_schema_returns_fields_in_sort_order():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get("/api/v1/external-api/templates/ext-template/schema", headers={"X-API-Key": read_key})
            assert response.status_code == 200, response.text
            body = response.json()
            assert [item["name"] for item in body] == ["cedula", "nombre"]
            assert body[0]["component_type"] == "DOCUMENT_ID"
            assert body[0]["label"] == "Cedula"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_get_external_template_schema_rejects_other_project_template():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            read_key = create_api_key(client, headers, ["records.read"])
            response = client.get("/api/v1/external-api/templates/ext-other-template/schema", headers={"X-API-Key": read_key})
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
