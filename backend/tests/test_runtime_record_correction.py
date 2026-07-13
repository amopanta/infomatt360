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
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="corr-project", name="Correccion")
        writer_role = Role(id="corr-writer-role", name="Capturista", permissions="records.write")
        outsider_role = Role(id="corr-outsider-role", name="Sin permiso", permissions="records.read")
        writer = User(id="corr-writer", full_name="Gestor", document_id="corr-writer-doc", email="corr-writer@example.com", password_hash=hash_password("Writer12345!"))
        outsider = User(id="corr-outsider", full_name="Sin permiso", document_id="corr-outsider-doc", email="corr-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        template = BuilderTemplate(id="corr-template", project_id=project.id, name="Plantilla", status="published")

        returned_record = RuntimeRecord(id="corr-record-returned", project_id=project.id, template_id=template.id, status="returned", submitted_by=writer.id, lock_version=1)
        submitted_record = RuntimeRecord(id="corr-record-submitted", project_id=project.id, template_id=template.id, status="submitted", submitted_by=writer.id, lock_version=1)

        db.add_all([
            project, writer_role, outsider_role, writer, outsider, template,
            returned_record, submitted_record,
            RuntimeRecordValue(record_id=returned_record.id, field_name="foto_entrega", field_value_json=json.dumps("blurry.jpg")),
            UserProjectAssignment(user_id=writer.id, project_id=project.id, role_id=writer_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
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


def test_correction_updates_existing_value_and_increments_lock_version():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-writer@example.com", "Writer12345!")
            response = client.patch(
                "/api/v1/runtime/record/corr-record-returned/correction",
                headers=headers,
                json={"field_name": "foto_entrega", "field_value_json": json.dumps("sharp.jpg"), "expected_lock_version": 1},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["lock_version"] == 2
            values = {item["field_name"]: json.loads(item["field_value_json"]) for item in body["values"]}
            assert values["foto_entrega"] == "sharp.jpg"

            with sessions() as db:
                record = db.get(RuntimeRecord, "corr-record-returned")
                assert record.lock_version == 2
                value = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record.id, RuntimeRecordValue.field_name == "foto_entrega").one()
                assert json.loads(value.field_value_json) == "sharp.jpg"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_correction_creates_value_for_a_field_that_did_not_exist_yet():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-writer@example.com", "Writer12345!")
            response = client.patch(
                "/api/v1/runtime/record/corr-record-returned/correction",
                headers=headers,
                json={"field_name": "observacion_nueva", "field_value_json": json.dumps("agregada en la correccion"), "expected_lock_version": 1},
            )
            assert response.status_code == 200, response.text
            values = {item["field_name"]: json.loads(item["field_value_json"]) for item in response.json()["values"]}
            assert values["observacion_nueva"] == "agregada en la correccion"
            assert values["foto_entrega"] == "blurry.jpg"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_correction_rejects_stale_lock_version_conflict():
    """Regresion de control de edicion concurrente: dos ediciones basadas en
    el mismo lock_version=1 -- la primera debe ganar, la segunda debe
    rechazarse con 409 en vez de sobrescribir en silencio."""
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-writer@example.com", "Writer12345!")

            first = client.patch(
                "/api/v1/runtime/record/corr-record-returned/correction",
                headers=headers,
                json={"field_name": "foto_entrega", "field_value_json": json.dumps("primera-correccion.jpg"), "expected_lock_version": 1},
            )
            assert first.status_code == 200

            second = client.patch(
                "/api/v1/runtime/record/corr-record-returned/correction",
                headers=headers,
                json={"field_name": "foto_entrega", "field_value_json": json.dumps("segunda-correccion-obsoleta.jpg"), "expected_lock_version": 1},
            )
            assert second.status_code == 409
            assert "modificado por otro usuario" in second.json()["detail"]

            with sessions() as db:
                value = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == "corr-record-returned", RuntimeRecordValue.field_name == "foto_entrega").one()
                assert json.loads(value.field_value_json) == "primera-correccion.jpg"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_correction_rejects_records_not_in_returned_status():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-writer@example.com", "Writer12345!")
            response = client.patch(
                "/api/v1/runtime/record/corr-record-submitted/correction",
                headers=headers,
                json={"field_name": "algun_campo", "field_value_json": json.dumps("x"), "expected_lock_version": 1},
            )
            assert response.status_code == 400
            assert "returned" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_correction_requires_records_write_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-outsider@example.com", "Outsider12345!")
            response = client.patch(
                "/api/v1/runtime/record/corr-record-returned/correction",
                headers=headers,
                json={"field_name": "foto_entrega", "field_value_json": json.dumps("x"), "expected_lock_version": 1},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_correction_returns_404_for_unknown_record():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "corr-writer@example.com", "Writer12345!")
            response = client.patch(
                "/api/v1/runtime/record/does-not-exist/correction",
                headers=headers,
                json={"field_name": "foto_entrega", "field_value_json": json.dumps("x"), "expected_lock_version": 1},
            )
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
