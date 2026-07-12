import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.integration_service as integration_service_module
from app.core.security import decrypt_text, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.integrations import IntegrationJob, IntegrationMap, IntegrationSource
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        manager = User(id="ds-manager", full_name="Administrador", document_id="ds-manager-doc", email="ds-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="ds-outsider", full_name="Sin acceso", document_id="ds-outsider-doc", email="ds-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        approver = User(id="ds-approver", full_name="Aprobador", document_id="ds-approver-doc", email="ds-approver@example.com", password_hash=hash_password("Approver12345!"))
        gestor = User(id="ds-gestor", full_name="Gestor", document_id="ds-gestor-doc", email="ds-gestor@example.com", password_hash=hash_password("Gestor12345!"))
        project = Project(id="ds-project", name="Proyecto Donante")
        manager_role = Role(id="ds-manager-role", name="Integraciones", permissions="integrations.donor_sync.manage,records.read")
        outsider_role = Role(id="ds-outsider-role", name="Sin permiso", permissions="records.read")
        approver_role = Role(id="ds-approver-role", name="Aprobador", permissions="records.approve,records.read")
        gestor_role = Role(id="ds-gestor-role", name="Gestor", permissions="records.write,records.read")
        template = BuilderTemplate(id="ds-template", project_id=project.id, name="Entrega beneficiarios", status="published")

        db.add_all([
            manager, outsider, approver, gestor, project,
            manager_role, outsider_role, approver_role, gestor_role, template,
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=gestor.id, project_id=project.id, role_id=gestor_role.id, status="active"),
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


def test_create_source_encrypts_credentials_and_never_exposes_them():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "ds-outsider@example.com", "Outsider12345!")
            denied = client.post(
                "/api/v1/integrations/sources",
                headers=outsider_headers,
                json={"project_id": "ds-project", "name": "ActivityInfo", "source_type": "activityinfo", "base_url": "https://api.activityinfo.example/records", "credentials": "secret-token"},
            )
            assert denied.status_code == 403

            manager_headers = auth(client, "ds-manager@example.com", "Manager12345!")
            response = client.post(
                "/api/v1/integrations/sources",
                headers=manager_headers,
                json={"project_id": "ds-project", "name": "ActivityInfo", "source_type": "activityinfo", "base_url": "https://api.activityinfo.example/records", "credentials": "secret-token"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["has_credentials"] is True
            assert "credentials" not in body
            assert "credentials_encrypted" not in body

            with sessions() as db:
                source = db.query(IntegrationSource).filter(IntegrationSource.id == body["id"]).first()
                assert source.credentials_encrypted != "secret-token"
                assert decrypt_text(source.credentials_encrypted) == "secret-token"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _create_source_and_map(sessions, *, base_url: str = "https://donor.example/api/records", credentials: str | None = "token-abc") -> tuple[str, str]:
    with sessions() as db:
        source = IntegrationSource(project_id="ds-project", name="Donante", source_type="activityinfo", base_url=base_url, status="active")
        if credentials:
            from app.core.security import encrypt_text
            source.credentials_encrypted = encrypt_text(credentials)
        db.add(source)
        db.flush()
        integration_map = IntegrationMap(
            source_id=source.id, template_id="ds-template", name="Mapeo beneficiarios",
            target_table="beneficiarios", fields_json=json.dumps({"documento": "national_id", "nombre": "full_name"}),
            status="active",
        )
        db.add(integration_map)
        db.commit()
        return source.id, integration_map.id


def _create_record(sessions, record_id: str) -> None:
    with sessions() as db:
        record = RuntimeRecord(id=record_id, project_id="ds-project", template_id="ds-template", status="submitted", submitted_by="ds-gestor")
        db.add(record)
        db.add(RuntimeRecordValue(record_id=record_id, field_name="documento", field_value_json=json.dumps("123456789")))
        db.add(RuntimeRecordValue(record_id=record_id, field_name="nombre", field_value_json=json.dumps("Ana Perez")))
        db.commit()


def test_approving_record_pushes_mapped_payload_to_donor_source():
    engine, sessions = setup_client()
    source_id, map_id = _create_source_and_map(sessions)
    _create_record(sessions, "ds-record-1")

    sent_requests = []
    original_post = integration_service_module.httpx.post

    def fake_post(url, **kwargs):
        sent_requests.append((url, kwargs))
        return FakeResponse(201, '{"id": "external-1"}')

    integration_service_module.httpx.post = fake_post
    try:
        with TestClient(app) as client:
            headers = auth(client, "ds-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "ds-project", "record_id": "ds-record-1", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            assert len(sent_requests) == 1
            url, kwargs = sent_requests[0]
            assert url == "https://donor.example/api/records"
            assert kwargs["json"] == {"national_id": "123456789", "full_name": "Ana Perez"}
            assert kwargs["headers"]["Authorization"] == "Bearer token-abc"

            with sessions() as db:
                job = db.query(IntegrationJob).filter(IntegrationJob.reference_record_id == "ds-record-1").first()
                assert job is not None
                assert job.status == "sent"
                assert job.map_id == map_id
                assert job.source_id == source_id
    finally:
        integration_service_module.httpx.post = original_post
        app.dependency_overrides.clear()
        engine.dispose()


def test_approving_record_records_failure_without_breaking_approval():
    engine, sessions = setup_client()
    _create_source_and_map(sessions)
    _create_record(sessions, "ds-record-2")

    original_post = integration_service_module.httpx.post
    integration_service_module.httpx.post = lambda url, **kwargs: FakeResponse(500, "donor api down")
    try:
        with TestClient(app) as client:
            headers = auth(client, "ds-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "ds-project", "record_id": "ds-record-2", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                record = db.get(RuntimeRecord, "ds-record-2")
                assert record.status == "approved"

                job = db.query(IntegrationJob).filter(IntegrationJob.reference_record_id == "ds-record-2").first()
                assert job.status == "failed"
                assert "500" in job.last_result
    finally:
        integration_service_module.httpx.post = original_post
        app.dependency_overrides.clear()
        engine.dispose()


def test_approving_record_without_map_is_a_noop():
    engine, sessions = setup_client()
    with sessions() as db:
        plain_template = BuilderTemplate(id="ds-plain-template", project_id="ds-project", name="Formulario normal", status="published")
        record = RuntimeRecord(id="ds-record-3", project_id="ds-project", template_id="ds-plain-template", status="submitted", submitted_by="ds-gestor")
        db.add_all([plain_template, record])
        db.commit()

    original_post = integration_service_module.httpx.post
    integration_service_module.httpx.post = lambda url, **kwargs: (_ for _ in ()).throw(AssertionError("no deberia llamarse"))
    try:
        with TestClient(app) as client:
            headers = auth(client, "ds-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "ds-project", "record_id": "ds-record-3", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                assert db.query(IntegrationJob).count() == 0
    finally:
        integration_service_module.httpx.post = original_post
        app.dependency_overrides.clear()
        engine.dispose()


def test_map_and_job_endpoints_require_project_permission_via_source():
    engine, sessions = setup_client()
    source_id, _map_id = _create_source_and_map(sessions)
    try:
        with TestClient(app) as client:
            manager_headers = auth(client, "ds-manager@example.com", "Manager12345!")
            response = client.get(f"/api/v1/integrations/maps/{source_id}", headers=manager_headers)
            assert response.status_code == 200
            assert len(response.json()) == 1

            outsider_headers = auth(client, "ds-outsider@example.com", "Outsider12345!")
            response = client.get(f"/api/v1/integrations/maps/{source_id}", headers=outsider_headers)
            assert response.status_code == 403

            response = client.post(
                "/api/v1/integrations/maps",
                headers=outsider_headers,
                json={"source_id": source_id, "name": "Otro mapeo", "target_table": "x", "fields_json": "{}"},
            )
            assert response.status_code == 403

            response = client.get(f"/api/v1/integrations/jobs/{source_id}", headers=manager_headers)
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_approving_record_blocks_ssrf_to_private_and_loopback_targets():
    """Regresion SSRF: un `base_url` que resuelve a loopback/red privada nunca
    debe generar una peticion saliente real; debe registrarse como fallo."""
    engine, sessions = setup_client()
    _create_source_and_map(sessions, base_url="http://127.0.0.1:9999/internal-admin")
    _create_record(sessions, "ds-record-ssrf")

    called = False

    def fail_if_called(url, **kwargs):
        nonlocal called
        called = True
        return FakeResponse(200, "no deberia llegar aqui")

    original_post = integration_service_module.httpx.post
    integration_service_module.httpx.post = fail_if_called
    try:
        with TestClient(app) as client:
            headers = auth(client, "ds-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "ds-project", "record_id": "ds-record-ssrf", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text
            assert called is False

            with sessions() as db:
                job = db.query(IntegrationJob).filter(IntegrationJob.reference_record_id == "ds-record-ssrf").first()
                assert job.status == "failed"
                assert "no permitida" in job.last_result or "resuelve" in job.last_result
    finally:
        integration_service_module.httpx.post = original_post
        app.dependency_overrides.clear()
        engine.dispose()


def test_approving_record_blocks_ssrf_via_invalid_scheme():
    engine, sessions = setup_client()
    _create_source_and_map(sessions, base_url="file:///etc/passwd")
    _create_record(sessions, "ds-record-scheme")

    called = False

    def fail_if_called(url, **kwargs):
        nonlocal called
        called = True
        return FakeResponse(200, "no deberia llegar aqui")

    original_post = integration_service_module.httpx.post
    integration_service_module.httpx.post = fail_if_called
    try:
        with TestClient(app) as client:
            headers = auth(client, "ds-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "ds-project", "record_id": "ds-record-scheme", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text
            assert called is False

            with sessions() as db:
                job = db.query(IntegrationJob).filter(IntegrationJob.reference_record_id == "ds-record-scheme").first()
                assert job.status == "failed"
    finally:
        integration_service_module.httpx.post = original_post
        app.dependency_overrides.clear()
        engine.dispose()
