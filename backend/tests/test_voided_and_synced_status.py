"""Pruebas de los estados 'anulado' (voided) y 'sincronizado' (synced),
ver docs/100 -- cierran el hallazgo #14 de la auditoria de trazabilidad
(docs/96): la maquina de estados de RuntimeRecord ahora tiene los 9 estados
minimos del Documento Maestro de Requerimientos v1.0.
"""

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
from app.models.review import ReviewAction
from app.models.runtime_record import RuntimeRecord


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        approver = User(id="voidtest-approver", full_name="Aprobador", document_id="voidtest-approver-doc", email="voidtest-approver@example.com", password_hash=hash_password("Approver12345!"))
        voider = User(id="voidtest-voider", full_name="Anulador", document_id="voidtest-voider-doc", email="voidtest-voider@example.com", password_hash=hash_password("Voider12345!"))
        outsider = User(id="voidtest-outsider", full_name="Sin permiso de anular", document_id="voidtest-outsider-doc", email="voidtest-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="voidtest-project", name="Estados voided/synced")
        approver_role = Role(id="voidtest-approver-role", name="Aprobador", permissions="records.approve")
        voider_role = Role(id="voidtest-voider-role", name="Anulador", permissions="records.void")
        outsider_role = Role(id="voidtest-outsider-role", name="Sin anular", permissions="records.approve")
        template = BuilderTemplate(id="voidtest-template", project_id=project.id, name="Plantilla", status="published")

        db.add_all([
            approver, voider, outsider, project, approver_role, voider_role, outsider_role, template,
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=voider.id, project_id=project.id, role_id=voider_role.id, status="active"),
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


def _create_record(sessions, record_id: str, status: str) -> None:
    with sessions() as db:
        db.add(RuntimeRecord(id=record_id, project_id="voidtest-project", template_id="voidtest-template", status=status, submitted_by="voidtest-approver"))
        db.commit()


def test_voiding_requires_records_void_permission():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-1", "submitted")
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "voidtest-outsider@example.com", "Outsider12345!")
            denied = client.post(
                "/api/v1/review/actions", headers=outsider_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-1", "to_status": "voided", "action": "void"},
            )
            assert denied.status_code == 403

            voider_headers = auth(client, "voidtest-voider@example.com", "Voider12345!")
            allowed = client.post(
                "/api/v1/review/actions", headers=voider_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-1", "to_status": "voided", "action": "void", "notes": "Duplicado detectado"},
            )
            assert allowed.status_code == 200, allowed.text

            with sessions() as db:
                record = db.get(RuntimeRecord, "voidtest-record-1")
                assert record.status == "voided"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_voided_is_terminal():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-2", "voided")
    try:
        with TestClient(app) as client:
            # El aprobador si tiene el permiso "records.approve" que exige
            # el estado destino "archived" -- esto prueba que la maquina de
            # estados en si rechaza la transicion, no solo el permiso.
            approver_headers = auth(client, "voidtest-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions", headers=approver_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-2", "to_status": "archived", "action": "archive"},
            )
            assert response.status_code == 400
            assert "no soportado" in response.json()["detail"].lower() or "no permitida" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_archived_and_rejected_records_can_still_be_voided():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-3", "archived")
    _create_record(sessions, "voidtest-record-4", "rejected")
    try:
        with TestClient(app) as client:
            voider_headers = auth(client, "voidtest-voider@example.com", "Voider12345!")
            for record_id in ("voidtest-record-3", "voidtest-record-4"):
                response = client.post(
                    "/api/v1/review/actions", headers=voider_headers,
                    json={"project_id": "voidtest-project", "record_id": record_id, "to_status": "voided", "action": "void"},
                )
                assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_manual_synced_transition_requires_records_approve():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-5", "approved")
    try:
        with TestClient(app) as client:
            voider_headers = auth(client, "voidtest-voider@example.com", "Voider12345!")
            denied = client.post(
                "/api/v1/review/actions", headers=voider_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-5", "to_status": "synced", "action": "mark_synced"},
            )
            assert denied.status_code == 403

            approver_headers = auth(client, "voidtest-approver@example.com", "Approver12345!")
            allowed = client.post(
                "/api/v1/review/actions", headers=approver_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-5", "to_status": "synced", "action": "mark_synced"},
            )
            assert allowed.status_code == 200, allowed.text

            with sessions() as db:
                record = db.get(RuntimeRecord, "voidtest-record-5")
                assert record.status == "synced"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_synced_can_still_be_archived_or_voided():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-6", "synced")
    try:
        with TestClient(app) as client:
            approver_headers = auth(client, "voidtest-approver@example.com", "Approver12345!")
            archived = client.post(
                "/api/v1/review/actions", headers=approver_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-6", "to_status": "archived", "action": "archive"},
            )
            assert archived.status_code == 200, archived.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_void_action_is_offered_in_next_actions_without_a_configured_flow():
    """Regresion: approval_flow_service.DEFAULT_ACTIONS no ofrecia "Anular" en
    proyectos sin flujo de aprobacion configurado (el caso comun), aunque el
    fallback del frontend si lo tenia -- el boton nunca se pintaba porque
    next_actions() con resultado no vacio siempre gana sobre el fallback.
    Solo se detecto probando en el navegador real, no con pruebas que llaman
    la API directo con to_status="voided"."""
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-8", "submitted")
    try:
        with TestClient(app) as client:
            voider_headers = auth(client, "voidtest-voider@example.com", "Voider12345!")
            response = client.get("/api/v1/review/records/voidtest-record-8/next-actions", headers=voider_headers)
            assert response.status_code == 200
            actions = response.json()
            void_actions = [item for item in actions if item["to_status"] == "voided"]
            assert len(void_actions) == 1
            assert void_actions[0]["action"] == "void"
            assert void_actions[0]["required_permission"] == "records.void"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_voiding_records_a_review_action_history_entry():
    engine, sessions = setup_client()
    _create_record(sessions, "voidtest-record-7", "submitted")
    try:
        with TestClient(app) as client:
            voider_headers = auth(client, "voidtest-voider@example.com", "Voider12345!")
            client.post(
                "/api/v1/review/actions", headers=voider_headers,
                json={"project_id": "voidtest-project", "record_id": "voidtest-record-7", "to_status": "voided", "action": "void", "notes": "Participante confirmo que nunca recibio la visita"},
            ).raise_for_status()

            history = client.get("/api/v1/review/records/voidtest-record-7/actions", headers=voider_headers)
            assert history.status_code == 200
            actions = history.json()
            assert len(actions) == 1
            assert actions[0]["from_status"] == "submitted"
            assert actions[0]["to_status"] == "voided"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
