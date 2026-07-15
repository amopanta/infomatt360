"""Pruebas del rol de "Administrador nacional" (asignacion a nivel de
Organizacion) y del rol predefinido "Auditor/Consulta", ver docs/101 --
cierra el hallazgo #12 de la auditoria de trazabilidad (docs/96).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserOrganizationAssignment, UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.organization import Organization


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        org_a = Organization(id="orgtest-org-a", name="Organizacion A", slug="orgtest-org-a")
        org_b = Organization(id="orgtest-org-b", name="Organizacion B", slug="orgtest-org-b")

        project_a1 = Project(id="orgtest-project-a1", name="Proyecto A1", organization_id=org_a.id, status="active")
        project_a2 = Project(id="orgtest-project-a2", name="Proyecto A2", organization_id=org_a.id, status="active")
        project_b1 = Project(id="orgtest-project-b1", name="Proyecto B1", organization_id=org_b.id, status="active")

        template_a1 = BuilderTemplate(id="orgtest-template-a1", project_id=project_a1.id, name="Plantilla A1", status="published")
        template_a2 = BuilderTemplate(id="orgtest-template-a2", project_id=project_a2.id, name="Plantilla A2", status="published")
        template_b1 = BuilderTemplate(id="orgtest-template-b1", project_id=project_b1.id, name="Plantilla B1", status="published")

        national_role = Role(id="orgtest-national-role", name="Administrador nacional", permissions="projects.read,records.read,records.write,records.review,records.approve,organizations.manage,identity.users.manage")
        auditor_role = Role(id="orgtest-auditor-role", name="Auditor/Consulta", permissions="projects.read,records.read,gis.read,messages.read,reports.export")
        no_manage_role = Role(id="orgtest-no-manage-role", name="Sin gestion de organizacion", permissions="records.read")

        national_user = User(id="orgtest-national-user", full_name="Admin Nacional", document_id="orgtest-national-doc", email="orgtest-national@example.com", password_hash=hash_password("National12345!"))
        auditor_user = User(id="orgtest-auditor-user", full_name="Auditor Org", document_id="orgtest-auditor-doc", email="orgtest-auditor@example.com", password_hash=hash_password("Auditor12345!"))
        outsider_user = User(id="orgtest-outsider-user", full_name="Sin gestion", document_id="orgtest-outsider-doc", email="orgtest-outsider@example.com", password_hash=hash_password("Outsider12345!"))

        db.add_all([
            org_a, org_b, project_a1, project_a2, project_b1,
            template_a1, template_a2, template_b1,
            national_role, auditor_role, no_manage_role,
            national_user, auditor_user, outsider_user,
            UserOrganizationAssignment(user_id=national_user.id, organization_id=org_a.id, role_id=national_role.id, status="active"),
            UserOrganizationAssignment(user_id=auditor_user.id, organization_id=org_a.id, role_id=auditor_role.id, status="active"),
            UserProjectAssignment(user_id=outsider_user.id, project_id=project_a1.id, role_id=no_manage_role.id, status="active"),
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


def test_organization_wide_assignment_grants_access_to_every_project_without_individual_assignment():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "orgtest-national@example.com", "National12345!")
            for template_id in ("orgtest-template-a1", "orgtest-template-a2"):
                response = client.get(f"/api/v1/runtime/template/{template_id}/records/search", headers=headers)
                assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_organization_wide_assignment_covers_a_project_created_after_the_assignment():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            new_project = Project(id="orgtest-project-a3", name="Proyecto A3 (posterior)", organization_id="orgtest-org-a", status="active")
            new_template = BuilderTemplate(id="orgtest-template-a3", project_id=new_project.id, name="Plantilla A3", status="published")
            db.add_all([new_project, new_template])
            db.commit()

        with TestClient(app) as client:
            headers = auth(client, "orgtest-national@example.com", "National12345!")
            response = client.get("/api/v1/runtime/template/orgtest-template-a3/records/search", headers=headers)
            assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_auditor_role_can_read_but_not_review_records():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            from app.models.runtime_record import RuntimeRecord
            db.add(RuntimeRecord(id="orgtest-record-1", project_id="orgtest-project-a1", template_id="orgtest-template-a1", status="submitted", submitted_by="orgtest-national-user"))
            db.commit()

        with TestClient(app) as client:
            headers = auth(client, "orgtest-auditor@example.com", "Auditor12345!")

            read_response = client.get("/api/v1/runtime/template/orgtest-template-a1/records/search", headers=headers)
            assert read_response.status_code == 200, read_response.text

            review_response = client.post(
                "/api/v1/review/actions", headers=headers,
                json={"project_id": "orgtest-project-a1", "record_id": "orgtest-record-1", "to_status": "under_review", "action": "start_review"},
            )
            assert review_response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_organization_assignment_does_not_cross_into_another_organization():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "orgtest-national@example.com", "National12345!")
            response = client.get("/api/v1/runtime/template/orgtest-template-b1/records/search", headers=headers)
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_project_level_assignment_still_works_without_any_organization_assignment():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "orgtest-outsider@example.com", "Outsider12345!")
            response = client.get("/api/v1/runtime/template/orgtest-template-a1/records/search", headers=headers)
            assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_creating_organization_assignment_requires_organizations_manage():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "orgtest-outsider@example.com", "Outsider12345!")
            denied = client.post(
                "/api/v1/organization-assignments/", headers=outsider_headers,
                json={"user_id": "orgtest-auditor-user", "organization_id": "orgtest-org-a", "role_id": "orgtest-auditor-role"},
            )
            assert denied.status_code == 403

            national_headers = auth(client, "orgtest-national@example.com", "National12345!")
            allowed = client.post(
                "/api/v1/organization-assignments/", headers=national_headers,
                json={"user_id": "orgtest-outsider-user", "organization_id": "orgtest-org-a", "role_id": "orgtest-auditor-role"},
            )
            assert allowed.status_code == 200, allowed.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_creating_project_assignment_requires_identity_users_manage():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "orgtest-outsider@example.com", "Outsider12345!")
            denied = client.post(
                "/api/v1/assignments/", headers=outsider_headers,
                json={"user_id": "orgtest-auditor-user", "project_id": "orgtest-project-a1", "role_id": "orgtest-auditor-role"},
            )
            assert denied.status_code == 403

            national_headers = auth(client, "orgtest-national@example.com", "National12345!")
            allowed = client.post(
                "/api/v1/assignments/", headers=national_headers,
                json={"user_id": "orgtest-auditor-user", "project_id": "orgtest-project-a1", "role_id": "orgtest-auditor-role"},
            )
            assert allowed.status_code == 200, allowed.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
