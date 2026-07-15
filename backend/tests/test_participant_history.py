"""Pruebas del participante como eje central (ver docs/98): enlace de
RuntimeRecord a Participant (explicito o por coincidencia de DOCUMENT_ID) y
el historial unificado entre plantillas.
"""

import json

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


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="history-project", name="Historial de participantes")
        other_project = Project(id="history-other-project", name="Otro proyecto")
        user = User(id="history-user", full_name="Gestor", document_id="history-user-doc", email="history-user@example.com", password_hash=hash_password("Gestor12345!"))

        template_a = BuilderTemplate(id="history-template-a", project_id=project.id, name="Censo agricola", status="published")
        template_b = BuilderTemplate(id="history-template-b", project_id=project.id, name="Seguimiento psicosocial", status="published")

        participant = Participant(id="history-participant", project_id=project.id, document_id="CC-777", full_name="Carlos Perez")
        other_participant = Participant(id="history-other-participant", project_id=other_project.id, document_id="CC-999", full_name="Otro proyecto")

        role = Role(id="history-role", name="Gestor", permissions="records.write,records.read")
        db.add_all([
            project, other_project, user, template_a, template_b, participant, other_participant, role,
            UserProjectAssignment(user_id=user.id, project_id=project.id, role_id=role.id, status="active"),
            BuilderComponent(template_id=template_a.id, component_type="DOCUMENT_ID", name="documento", label="Documento", sort_order=0),
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


def test_explicit_participant_id_links_record():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/runtime/save",
                headers=headers,
                json={
                    "project_id": "history-project", "template_id": "history-template-b",
                    "participant_id": "history-participant",
                    "values": [{"field_name": "observacion", "field_value_json": '"Visita inicial"'}],
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["participant_id"] == "history-participant"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_explicit_participant_id_rejects_other_project():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/runtime/save",
                headers=headers,
                json={
                    "project_id": "history-project", "template_id": "history-template-b",
                    "participant_id": "history-other-participant",
                    "values": [],
                },
            )
            assert response.status_code == 403
            assert "otro proyecto" in response.text.lower()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_explicit_participant_id_rejects_nonexistent():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/runtime/save",
                headers=headers,
                json={
                    "project_id": "history-project", "template_id": "history-template-b",
                    "participant_id": "does-not-exist",
                    "values": [],
                },
            )
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_auto_links_by_document_id_field_value():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/runtime/save",
                headers=headers,
                json={
                    "project_id": "history-project", "template_id": "history-template-a",
                    "values": [{"field_name": "documento", "field_value_json": '"CC-777"'}],
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["participant_id"] == "history-participant"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_auto_link_does_not_match_unknown_document():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.post(
                "/api/v1/runtime/save",
                headers=headers,
                json={
                    "project_id": "history-project", "template_id": "history-template-a",
                    "values": [{"field_name": "documento", "field_value_json": '"CC-000-desconocido"'}],
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["participant_id"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_unified_history_spans_templates_and_channels():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")

            # Captura via auto-enlace por documento (plantilla A).
            client.post(
                "/api/v1/runtime/save", headers=headers,
                json={"project_id": "history-project", "template_id": "history-template-a",
                      "values": [{"field_name": "documento", "field_value_json": '"CC-777"'}]},
            ).raise_for_status()

            # Captura via enlace explicito (plantilla B) -- otro canal/formulario.
            client.post(
                "/api/v1/runtime/save", headers=headers,
                json={"project_id": "history-project", "template_id": "history-template-b",
                      "participant_id": "history-participant", "values": []},
            ).raise_for_status()

            history = client.get("/api/v1/participants/history-participant/history", headers=headers)
            assert history.status_code == 200, history.text
            items = history.json()
            assert len(items) == 2
            template_names = {item["template_name"] for item in items}
            assert template_names == {"Censo agricola", "Seguimiento psicosocial"}
            assert all(item["record_id"] for item in items)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_participant_from_another_project_is_not_visible():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "history-user@example.com", "Gestor12345!")
            response = client.get("/api/v1/participants/history-other-participant", headers=headers)
            assert response.status_code == 404

            history = client.get("/api/v1/participants/history-other-participant/history", headers=headers)
            assert history.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
