import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.ai_audit_service as ai_audit_service_module
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.ai import AiAuditConfig, AiCheck
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _enable_provider(provider: str = "anthropic"):
    originals = (settings.ai_audit_provider, settings.ai_audit_api_key, settings.ai_audit_base_url, settings.ai_audit_model)
    settings.ai_audit_provider = provider
    settings.ai_audit_api_key = "test-llm-key"
    settings.ai_audit_base_url = ""
    settings.ai_audit_model = ""
    return originals


def _restore_provider(originals):
    settings.ai_audit_provider, settings.ai_audit_api_key, settings.ai_audit_base_url, settings.ai_audit_model = originals


def _anthropic_response(risk_level: str) -> FakeResponse:
    body = json.dumps({"risk_level": risk_level, "reasoning": "prueba", "flagged_phrases": ["frase de prueba"]})
    return FakeResponse(200, {"content": [{"text": body}]})


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        approver = User(id="aud-approver", full_name="Aprobador", document_id="aud-approver-doc", email="aud-approver@example.com", password_hash=hash_password("Approver12345!"))
        manager = User(id="aud-manager", full_name="Administrador IA", document_id="aud-manager-doc", email="aud-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="aud-outsider", full_name="Sin permiso", document_id="aud-outsider-doc", email="aud-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="aud-project", name="Proyecto Auditoria")
        approver_role = Role(id="aud-approver-role", name="Aprobador", permissions="records.write,records.read")
        manager_role = Role(id="aud-manager-role", name="IA Manager", permissions="ai.audit.manage,records.read")
        outsider_role = Role(id="aud-outsider-role", name="Sin permiso", permissions="records.read")
        template = BuilderTemplate(id="aud-template", project_id=project.id, name="Entrega con observaciones", status="published")

        db.add_all([
            approver, manager, outsider, project,
            approver_role, manager_role, outsider_role, template,
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
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


def _create_config(sessions, mode: str) -> None:
    with sessions() as db:
        db.add(AiAuditConfig(template_id="aud-template", text_field_name="observaciones", mode=mode))
        db.commit()


def _save_record(client, headers, record_text: str) -> dict:
    response = client.post(
        "/api/v1/runtime/save",
        headers=headers,
        json={
            "project_id": "aud-project",
            "template_id": "aud-template",
            "status": "submitted",
            "values": [{"field_name": "observaciones", "field_value_json": json.dumps(record_text)}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_config_requires_ai_audit_manage_permission():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "aud-outsider@example.com", "Outsider12345!")
            denied = client.post("/api/v1/ai-audit/config", headers=outsider_headers, json={"template_id": "aud-template", "text_field_name": "observaciones", "mode": "human"})
            assert denied.status_code == 403

            manager_headers = auth(client, "aud-manager@example.com", "Manager12345!")
            response = client.post("/api/v1/ai-audit/config", headers=manager_headers, json={"template_id": "aud-template", "text_field_name": "observaciones", "mode": "human"})
            assert response.status_code == 200, response.text
            assert response.json()["mode"] == "human"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_saving_record_without_config_is_a_noop():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "Todo entregado sin novedad")
            with sessions() as db:
                assert db.query(AiCheck).filter(AiCheck.record_id == data["id"]).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_saving_record_without_provider_configured_is_recorded_as_skipped():
    engine, sessions = setup_client()
    _create_config(sessions, "automatic")
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "El beneficiario recibio todo conforme")
            assert data["status"] == "submitted"
            with sessions() as db:
                check = db.query(AiCheck).filter(AiCheck.record_id == data["id"]).first()
                assert check.status == "skipped"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_human_mode_never_auto_rejects_even_on_high_risk():
    engine, sessions = setup_client()
    _create_config(sessions, "human")
    originals = _enable_provider()
    original_post = ai_audit_service_module.httpx.post
    ai_audit_service_module.httpx.post = lambda url, **kwargs: _anthropic_response("high")
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "Se entrego el kit pero faltaron dos herramientas")
            assert data["status"] == "submitted"
            with sessions() as db:
                check = db.query(AiCheck).filter(AiCheck.record_id == data["id"]).first()
                assert check.status == "high"
    finally:
        ai_audit_service_module.httpx.post = original_post
        _restore_provider(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_automatic_mode_rejects_on_possible_risk():
    engine, sessions = setup_client()
    _create_config(sessions, "automatic")
    originals = _enable_provider()
    original_post = ai_audit_service_module.httpx.post
    ai_audit_service_module.httpx.post = lambda url, **kwargs: _anthropic_response("possible")
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "Se realizo el acta por telefono, no fue posible llegar a la vereda")
            with sessions() as db:
                record = db.get(RuntimeRecord, data["id"])
                assert record.status == "rejected"
    finally:
        ai_audit_service_module.httpx.post = original_post
        _restore_provider(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_mixed_mode_only_rejects_on_high_risk_not_possible():
    engine, sessions = setup_client()
    _create_config(sessions, "mixed")
    originals = _enable_provider()
    original_post = ai_audit_service_module.httpx.post
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")

            ai_audit_service_module.httpx.post = lambda url, **kwargs: _anthropic_response("possible")
            data_possible = _save_record(client, headers, "Observacion ambigua")
            with sessions() as db:
                record = db.get(RuntimeRecord, data_possible["id"])
                assert record.status == "submitted"

            ai_audit_service_module.httpx.post = lambda url, **kwargs: _anthropic_response("high")
            data_high = _save_record(client, headers, "Observacion con fraude evidente")
            with sessions() as db:
                record = db.get(RuntimeRecord, data_high["id"])
                assert record.status == "rejected"
    finally:
        ai_audit_service_module.httpx.post = original_post
        _restore_provider(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_llm_network_failure_is_recorded_as_error_without_blocking_save():
    engine, sessions = setup_client()
    _create_config(sessions, "automatic")
    originals = _enable_provider()
    original_post = ai_audit_service_module.httpx.post

    def failing_post(url, **kwargs):
        raise ai_audit_service_module.httpx.HTTPError("timeout")

    ai_audit_service_module.httpx.post = failing_post
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "Observaciones normales")
            assert data["status"] == "submitted"
            with sessions() as db:
                check = db.query(AiCheck).filter(AiCheck.record_id == data["id"]).first()
                assert check.status == "error"
    finally:
        ai_audit_service_module.httpx.post = original_post
        _restore_provider(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_openai_compatible_provider_sends_expected_request_shape():
    engine, sessions = setup_client()
    _create_config(sessions, "human")
    originals = _enable_provider("openai_compatible")
    settings.ai_audit_base_url = "https://api.deepseek.com/v1"
    settings.ai_audit_model = "deepseek-chat"

    sent = {}
    original_post = ai_audit_service_module.httpx.post

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent["json"] = kwargs["json"]
        sent["headers"] = kwargs["headers"]
        return FakeResponse(200, {"choices": [{"message": {"content": json.dumps({"risk_level": "none", "reasoning": "ok", "flagged_phrases": []})}}]})

    ai_audit_service_module.httpx.post = fake_post
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            _save_record(client, headers, "Todo en orden")
            assert sent["url"] == "https://api.deepseek.com/v1/chat/completions"
            assert sent["json"]["model"] == "deepseek-chat"
            assert sent["headers"]["Authorization"] == "Bearer test-llm-key"
    finally:
        ai_audit_service_module.httpx.post = original_post
        _restore_provider(originals)
        app.dependency_overrides.clear()
        engine.dispose()


def test_manual_analyze_endpoint_requires_permission():
    engine, sessions = setup_client()
    _create_config(sessions, "human")
    try:
        with TestClient(app) as client:
            headers = auth(client, "aud-approver@example.com", "Approver12345!")
            data = _save_record(client, headers, "Sin novedad")
            record_id = data["id"]

            outsider_headers = auth(client, "aud-outsider@example.com", "Outsider12345!")
            denied = client.post(f"/api/v1/ai-audit/records/{record_id}/analyze", headers=outsider_headers)
            assert denied.status_code == 403

            manager_headers = auth(client, "aud-manager@example.com", "Manager12345!")
            response = client.post(f"/api/v1/ai-audit/records/{record_id}/analyze", headers=manager_headers)
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
