from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.whatsapp_service as whatsapp_module
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord
from app.models.whatsapp import WhatsAppNotification


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def _enable_waha_config():
    originals = (settings.waha_base_url, settings.waha_api_key, settings.waha_session)
    settings.waha_base_url = "https://waha.example.com"
    settings.waha_api_key = "test-key"
    settings.waha_session = "default"
    return originals


def _restore_waha_config(originals):
    settings.waha_base_url, settings.waha_api_key, settings.waha_session = originals


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        approver = User(id="wa-approver", full_name="Aprobador", document_id="wa-approver-doc", email="wa-approver@example.com", password_hash=hash_password("Approver12345!"))
        gestor_with_phone = User(id="wa-gestor-phone", full_name="Gestor con telefono", document_id="wa-gestor-phone-doc", email="wa-gestor-phone@example.com", password_hash=hash_password("Gestor12345!"), phone="+57 300 123 4567")
        gestor_without_phone = User(id="wa-gestor-nophone", full_name="Gestor sin telefono", document_id="wa-gestor-nophone-doc", email="wa-gestor-nophone@example.com", password_hash=hash_password("Gestor12345!"))
        outsider = User(id="wa-outsider", full_name="Sin acceso", document_id="wa-outsider-doc", email="wa-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="wa-project", name="Proyecto WhatsApp")
        approver_role = Role(id="wa-approver-role", name="Aprobador", permissions="records.approve,records.read")
        gestor_role = Role(id="wa-gestor-role", name="Gestor", permissions="records.write,records.read")
        outsider_role = Role(id="wa-outsider-role", name="Sin permiso", permissions="records.write")
        template = BuilderTemplate(id="wa-template", project_id=project.id, name="Formulario", status="published")

        db.add_all([
            approver, gestor_with_phone, gestor_without_phone, outsider, project,
            approver_role, gestor_role, outsider_role, template,
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=gestor_with_phone.id, project_id=project.id, role_id=gestor_role.id, status="active"),
            UserProjectAssignment(user_id=gestor_without_phone.id, project_id=project.id, role_id=gestor_role.id, status="active"),
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


def _create_record(sessions, record_id: str, submitted_by: str) -> None:
    with sessions() as db:
        db.add(RuntimeRecord(id=record_id, project_id="wa-project", template_id="wa-template", status="submitted", submitted_by=submitted_by))
        db.commit()


def test_rejecting_record_sends_whatsapp_when_configured_and_owner_has_phone():
    engine, sessions = setup_client()
    originals = _enable_waha_config()
    _create_record(sessions, "wa-record-1", "wa-gestor-phone")

    sent_requests = []

    def fake_post(url, **kwargs):
        sent_requests.append((url, kwargs))
        return FakeResponse(201, "")

    import httpx
    import app.services.whatsapp_service as whatsapp_service_module
    original_post = httpx.post
    whatsapp_service_module.httpx.post = fake_post
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={
                    "project_id": "wa-project",
                    "record_id": "wa-record-1",
                    "to_status": "rejected",
                    "action": "reject",
                    "notes": "Foto borrosa",
                    "rejected_field_name": "foto_evidencia",
                },
            )
            assert response.status_code == 200, response.text

            assert len(sent_requests) == 1
            url, kwargs = sent_requests[0]
            assert url == "https://waha.example.com/api/sendText"
            assert kwargs["json"]["chatId"] == "573001234567@c.us"
            assert "/records/wa-template?recordId=wa-record-1&campo=foto_evidencia" in kwargs["json"]["text"]
            assert "Campo a corregir: foto_evidencia" in kwargs["json"]["text"]
            assert kwargs["headers"]["X-Api-Key"] == "test-key"

            with sessions() as db:
                notification = db.query(WhatsAppNotification).filter(WhatsAppNotification.reference_record_id == "wa-record-1").first()
                assert notification is not None
                assert notification.status == "sent"
                assert notification.recipient_phone == "+57 300 123 4567"
    finally:
        whatsapp_service_module.httpx.post = original_post
        _restore_waha_config(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_rejecting_record_records_failure_without_breaking_the_review_action():
    engine, sessions = setup_client()
    originals = _enable_waha_config()
    _create_record(sessions, "wa-record-2", "wa-gestor-phone")

    import app.services.whatsapp_service as whatsapp_service_module
    original_post = whatsapp_service_module.httpx.post

    def failing_post(url, **kwargs):
        return FakeResponse(500, "gateway caido")

    whatsapp_service_module.httpx.post = failing_post
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "wa-project", "record_id": "wa-record-2", "to_status": "rejected", "action": "reject"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                notification = db.query(WhatsAppNotification).filter(WhatsAppNotification.reference_record_id == "wa-record-2").first()
                assert notification.status == "failed"
                assert "500" in notification.error
    finally:
        whatsapp_service_module.httpx.post = original_post
        _restore_waha_config(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_rejecting_record_without_waha_configured_is_recorded_as_skipped():
    engine, sessions = setup_client()
    _create_record(sessions, "wa-record-3", "wa-gestor-phone")
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "wa-project", "record_id": "wa-record-3", "to_status": "rejected", "action": "reject"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                notification = db.query(WhatsAppNotification).filter(WhatsAppNotification.reference_record_id == "wa-record-3").first()
                assert notification.status == "skipped"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_approving_record_does_not_trigger_whatsapp():
    engine, sessions = setup_client()
    originals = _enable_waha_config()
    _create_record(sessions, "wa-record-4", "wa-gestor-phone")
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "wa-project", "record_id": "wa-record-4", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                assert db.query(WhatsAppNotification).filter(WhatsAppNotification.reference_record_id == "wa-record-4").count() == 0
    finally:
        _restore_waha_config(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_rejecting_record_without_owner_phone_does_not_attempt_send():
    engine, sessions = setup_client()
    originals = _enable_waha_config()
    _create_record(sessions, "wa-record-5", "wa-gestor-nophone")
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "wa-project", "record_id": "wa-record-5", "to_status": "rejected", "action": "reject"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                assert db.query(WhatsAppNotification).filter(WhatsAppNotification.reference_record_id == "wa-record-5").count() == 0
    finally:
        _restore_waha_config(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_notifications_requires_project_permission():
    engine, sessions = setup_client()
    _create_record(sessions, "wa-record-6", "wa-gestor-phone")
    try:
        with TestClient(app) as client:
            headers = auth(client, "wa-approver@example.com", "Approver12345!")
            client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "wa-project", "record_id": "wa-record-6", "to_status": "rejected", "action": "reject"},
            )

            response = client.get("/api/v1/whatsapp/notifications/project/wa-project", headers=headers)
            assert response.status_code == 200
            assert len(response.json()) == 1

            outsider_headers = auth(client, "wa-outsider@example.com", "Outsider12345!")
            response = client.get("/api/v1/whatsapp/notifications/project/wa-project", headers=outsider_headers)
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
