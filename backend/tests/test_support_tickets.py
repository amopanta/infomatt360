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
        project = Project(id="support-project", name="Support Project")
        gestor_role = Role(id="support-gestor-role", name="Gestor", permissions="records.write")
        manager_role = Role(id="support-manager-role", name="Soporte", permissions="support.tickets.manage")

        gestor = User(id="support-gestor", full_name="Gestor", document_id="support-gestor-doc", email="support-gestor@example.com", password_hash=hash_password("Gestor12345!"))
        manager = User(id="support-manager", full_name="Soporte", document_id="support-manager-doc", email="support-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="support-outsider", full_name="Outsider", document_id="support-outsider-doc", email="support-outsider@example.com", password_hash=hash_password("Outsider12345!"))

        db.add_all([
            project,
            gestor_role,
            manager_role,
            gestor,
            manager,
            outsider,
            UserProjectAssignment(user_id=gestor.id, project_id=project.id, role_id=gestor_role.id, status="active"),
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
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


def test_create_ticket_requires_project_access():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "support-outsider@example.com", "Outsider12345!")
            response = client.post(
                "/api/v1/support/tickets",
                headers=headers,
                json={"project_id": "support-project", "subject": "No sincroniza", "description": "La app no sincroniza desde ayer"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_sync_keyword_auto_resolves_with_tutorial():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "support-gestor@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/support/tickets",
                headers=headers,
                json={"project_id": "support-project", "subject": "Falla sincronizacion", "description": "La tablet no sincroniza los registros desde ayer"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "auto_resolved"
            assert body["resolution_channel"] == "auto"
            assert body["matched_rule"] == "sync_help"
            assert body["auto_response_text"]
            assert body["resolved_at"] is not None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_gps_keyword_auto_resolves():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "support-gestor@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/support/tickets",
                headers=headers,
                json={"project_id": "support-project", "subject": "GPS", "description": "El dispositivo no lee el GPS en la vereda"},
            )
            assert response.status_code == 200
            assert response.json()["matched_rule"] == "gps_help"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_physical_damage_always_escalates_to_human_even_with_sync_keyword():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "support-gestor@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/support/tickets",
                headers=headers,
                json={"project_id": "support-project", "subject": "Tablet dañada", "description": "No sincroniza porque la pantalla rota no responde al tacto"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "open"
            assert body["resolution_channel"] == "human"
            assert body["matched_rule"] == "physical_damage"
            assert body["auto_response_text"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_unrecognized_description_escalates_to_human():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "support-gestor@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/support/tickets",
                headers=headers,
                json={"project_id": "support-project", "subject": "Duda", "description": "No entiendo como diligenciar la seccion de anexos del formulario"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "open"
            assert body["resolution_channel"] == "human"
            assert body["matched_rule"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_human_resolves_escalated_ticket():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            gestor_headers = auth(client, "support-gestor@example.com", "Gestor12345!")
            ticket = client.post(
                "/api/v1/support/tickets",
                headers=gestor_headers,
                json={"project_id": "support-project", "subject": "Duda", "description": "No entiendo la seccion de anexos"},
            ).json()

            manager_headers = auth(client, "support-manager@example.com", "Manager12345!")
            denied = client.post(f"/api/v1/support/tickets/{ticket['id']}/resolve", headers=gestor_headers, json={})
            assert denied.status_code == 403

            resolved = client.post(f"/api/v1/support/tickets/{ticket['id']}/resolve", headers=manager_headers, json={})
            assert resolved.status_code == 200
            assert resolved.json()["status"] == "resolved"
            assert resolved.json()["resolved_by"] == "support-manager"

            listed = client.get("/api/v1/support/tickets/project/support-project", headers=manager_headers)
            assert listed.status_code == 200
            assert len(listed.json()) == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
