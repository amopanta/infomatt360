"""Pruebas de la promocion base abierta -> base cerrada (ver docs/99):
enlazar o crear un participante a partir de un registro capturado sin
enlace previo, y el filtro de "sin participante enlazado" en la busqueda.
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
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.participants import Participant


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="promote-project", name="Promocion de participantes")
        reviewer_role = Role(id="promote-reviewer-role", name="Revisor", permissions="records.review")
        capturer_role = Role(id="promote-capturer-role", name="Capturista", permissions="records.write")
        reviewer = User(id="promote-reviewer", full_name="Revisor", document_id="promote-reviewer-doc", email="promote-reviewer@example.com", password_hash=hash_password("Reviewer12345!"))
        capturer = User(id="promote-capturer", full_name="Capturista", document_id="promote-capturer-doc", email="promote-capturer@example.com", password_hash=hash_password("Capturer12345!"))

        template = BuilderTemplate(id="promote-template", project_id=project.id, name="Censo abierto", status="published")
        existing_participant = Participant(id="promote-existing-participant", project_id=project.id, document_id="CC-500", full_name="Participante ya existente")

        db.add_all([
            project, reviewer_role, capturer_role, reviewer, capturer, template, existing_participant,
            UserProjectAssignment(user_id=reviewer.id, project_id=project.id, role_id=reviewer_role.id, status="active"),
            UserProjectAssignment(user_id=capturer.id, project_id=project.id, role_id=capturer_role.id, status="active"),
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


def _capture_unlinked_record(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/runtime/save",
        headers=headers,
        json={"project_id": "promote-project", "template_id": "promote-template", "values": [{"field_name": "nombre", "field_value_json": '"Nueva persona"'}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["participant_id"] is None
    return response.json()["id"]


def test_promote_creates_a_new_participant():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            capturer_headers = auth(client, "promote-capturer@example.com", "Capturer12345!")
            reviewer_headers = auth(client, "promote-reviewer@example.com", "Reviewer12345!")
            record_id = _capture_unlinked_record(client, capturer_headers)

            response = client.post(
                "/api/v1/participants/promote",
                headers=reviewer_headers,
                json={"record_id": record_id, "full_name": "Nueva persona", "document_id": "CC-NEW-1"},
            )
            assert response.status_code == 200, response.text
            participant = response.json()
            assert participant["full_name"] == "Nueva persona"

            record = client.get(f"/api/v1/runtime/record/{record_id}", headers=reviewer_headers).json()
            assert record["participant_id"] == participant["id"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_promote_links_to_existing_participant():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            capturer_headers = auth(client, "promote-capturer@example.com", "Capturer12345!")
            reviewer_headers = auth(client, "promote-reviewer@example.com", "Reviewer12345!")
            record_id = _capture_unlinked_record(client, capturer_headers)

            response = client.post(
                "/api/v1/participants/promote",
                headers=reviewer_headers,
                json={"record_id": record_id, "participant_id": "promote-existing-participant"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["id"] == "promote-existing-participant"

            record = client.get(f"/api/v1/runtime/record/{record_id}", headers=reviewer_headers).json()
            assert record["participant_id"] == "promote-existing-participant"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_promote_rejects_already_linked_record():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            capturer_headers = auth(client, "promote-capturer@example.com", "Capturer12345!")
            reviewer_headers = auth(client, "promote-reviewer@example.com", "Reviewer12345!")
            record_id = _capture_unlinked_record(client, capturer_headers)

            first = client.post(
                "/api/v1/participants/promote", headers=reviewer_headers,
                json={"record_id": record_id, "participant_id": "promote-existing-participant"},
            )
            assert first.status_code == 200

            second = client.post(
                "/api/v1/participants/promote", headers=reviewer_headers,
                json={"record_id": record_id, "full_name": "Otro nombre"},
            )
            assert second.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_promote_requires_review_permission():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            capturer_headers = auth(client, "promote-capturer@example.com", "Capturer12345!")
            record_id = _capture_unlinked_record(client, capturer_headers)

            response = client.post(
                "/api/v1/participants/promote", headers=capturer_headers,
                json={"record_id": record_id, "full_name": "Nueva persona"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_promote_requires_participant_id_or_full_name():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            reviewer_headers = auth(client, "promote-reviewer@example.com", "Reviewer12345!")
            response = client.post("/api/v1/participants/promote", headers=reviewer_headers, json={"record_id": "does-not-matter"})
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_unlinked_only_filter_on_records_search():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            capturer_headers = auth(client, "promote-capturer@example.com", "Capturer12345!")
            reviewer_headers = auth(client, "promote-reviewer@example.com", "Reviewer12345!")

            unlinked_id = _capture_unlinked_record(client, capturer_headers)
            linked = client.post(
                "/api/v1/runtime/save", headers=capturer_headers,
                json={"project_id": "promote-project", "template_id": "promote-template", "participant_id": "promote-existing-participant", "values": []},
            )
            assert linked.status_code == 200

            all_records = client.get("/api/v1/runtime/template/promote-template/records/search", headers=reviewer_headers)
            assert all_records.json()["total"] == 2

            only_unlinked = client.get("/api/v1/runtime/template/promote-template/records/search?unlinked_only=true", headers=reviewer_headers)
            assert only_unlinked.status_code == 200
            body = only_unlinked.json()
            assert body["total"] == 1
            assert body["items"][0]["id"] == unlinked_id
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
