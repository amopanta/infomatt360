"""Carga masiva de registros Runtime con sesion de usuario normal (ver
docs/106) -- cierra el hallazgo SYNC-001 de la auditoria tecnica de julio
2026: el cliente offline sincronizaba un registro por solicitud HTTP,
secuencial. Distinto de /runtime/bulk/save (API key, integraciones
externas, ver test_runtime_bulk_api_key.py).
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
from app.models.runtime_record import RuntimeRecord


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="sbulk-project", name="Sync bulk")
        other_project = Project(id="sbulk-other-project", name="Otro proyecto")
        template = BuilderTemplate(id="sbulk-template", project_id=project.id, name="Formulario", status="published")
        other_template = BuilderTemplate(id="sbulk-other-template", project_id=other_project.id, name="Otro formulario", status="published")
        writer_role = Role(id="sbulk-writer-role", name="Capturista", permissions="records.write,records.read")
        reader_role = Role(id="sbulk-reader-role", name="Solo lectura", permissions="records.read")
        writer = User(id="sbulk-writer", full_name="Capturista", document_id="sbulk-writer-doc", email="sbulk-writer@example.com", password_hash=hash_password("Writer12345!"))
        reader = User(id="sbulk-reader", full_name="Solo lectura", document_id="sbulk-reader-doc", email="sbulk-reader@example.com", password_hash=hash_password("Reader12345!"))
        db.add_all([
            project, other_project, template, other_template, writer_role, reader_role, writer, reader,
            UserProjectAssignment(user_id=writer.id, project_id=project.id, role_id=writer_role.id, status="active"),
            UserProjectAssignment(user_id=reader.id, project_id=project.id, role_id=reader_role.id, status="active"),
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


def _batch_payload(idempotency_key: str | None = None) -> dict:
    return {
        "project_id": "sbulk-project",
        "template_id": "sbulk-template",
        "idempotency_key": idempotency_key,
        "records": [
            {"project_id": "sbulk-project", "template_id": "sbulk-template", "values": [{"field_name": "nombre", "field_value_json": json.dumps("Ana")}]},
            {"project_id": "sbulk-project", "template_id": "sbulk-template", "values": [{"field_name": "nombre", "field_value_json": json.dumps("Beatriz")}]},
        ],
    }


def test_session_bulk_save_requires_records_write():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            reader_headers = auth(client, "sbulk-reader@example.com", "Reader12345!")
            denied = client.post("/api/v1/runtime/session/bulk-save", headers=reader_headers, json=_batch_payload())
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_session_bulk_save_creates_records_attributed_to_the_real_user():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            writer_headers = auth(client, "sbulk-writer@example.com", "Writer12345!")
            response = client.post("/api/v1/runtime/session/bulk-save", headers=writer_headers, json=_batch_payload("batch-001"))
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["received"] == 2
            assert data["created"] == 2
            assert data["failed"] == 0
            assert len(data["results"]) == 2

            with sessions() as db:
                records = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "sbulk-template").all()
                assert len(records) == 2
                assert all(record.submitted_by == "sbulk-writer" for record in records)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_session_bulk_save_idempotency_key_does_not_duplicate_on_retry():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            writer_headers = auth(client, "sbulk-writer@example.com", "Writer12345!")
            first = client.post("/api/v1/runtime/session/bulk-save", headers=writer_headers, json=_batch_payload("batch-retry"))
            assert first.status_code == 200
            assert first.json()["replayed"] is False

            second = client.post("/api/v1/runtime/session/bulk-save", headers=writer_headers, json=_batch_payload("batch-retry"))
            assert second.status_code == 200
            assert second.json()["replayed"] is True

            with sessions() as db:
                records = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "sbulk-template").all()
                assert len(records) == 2  # no se duplico en el reintento
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_session_bulk_save_rejects_template_from_another_project():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            writer_headers = auth(client, "sbulk-writer@example.com", "Writer12345!")
            payload = _batch_payload()
            payload["template_id"] = "sbulk-other-template"
            response = client.post("/api/v1/runtime/session/bulk-save", headers=writer_headers, json=payload)
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_session_bulk_save_rejects_nonexistent_template():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            writer_headers = auth(client, "sbulk-writer@example.com", "Writer12345!")
            payload = _batch_payload()
            payload["template_id"] = "does-not-exist"
            response = client.post("/api/v1/runtime/session/bulk-save", headers=writer_headers, json=payload)
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
