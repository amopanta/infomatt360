from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.case_management import UserTerritory
from app.models.identity import Project, Role, User
from app.models.messages import InternalMessage
from app.models.participants import Participant
from app.models.builder import BuilderTemplate
from app.models.runtime_record import RuntimeRecord
from app.models.scheduler import ScheduledTask
from app.services.scheduler_service import scheduler_service


def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add_all([
            Project(id="case-project", name="Casos"),
            Role(id="case-manager-role", name="Manager", permissions="identity.users.manage,records.read,records.write,reports.export"),
            Role(id="case-worker-role", name="Worker", permissions="records.read,records.write"),
            User(id="case-manager", full_name="Manager", document_id="case-manager-doc", email="case-manager@example.com", password_hash=hash_password("Manager12345!")),
            User(id="case-worker", full_name="Worker", document_id="case-worker-doc", email="case-worker@example.com", password_hash=hash_password("Worker12345!")),
            UserProjectAssignment(user_id="case-manager", project_id="case-project", role_id="case-manager-role"),
            UserProjectAssignment(user_id="case-worker", project_id="case-project", role_id="case-worker-role"),
            Participant(id="case-participant", project_id="case-project", full_name="Ana", metadata_json='{"department":"Cundinamarca","municipality":"Soacha"}'),
            Participant(id="other-participant", project_id="case-project", full_name="Beto", metadata_json='{"department":"Antioquia","municipality":"Medellín"}'),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_territory_filters_participants_and_case_reminder():
    engine, sessions = setup()
    try:
        with TestClient(app) as client:
            manager = auth(client, "case-manager@example.com", "Manager12345!")
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            assigned = client.post("/api/v1/territories/case-project", headers=manager, json={
                "user_id": "case-worker", "department": "Cundinamarca", "municipality": "Soacha"})
            assert assigned.status_code == 200, assigned.text
            visible = client.get("/api/v1/participants/project/case-project", headers=worker)
            assert [item["id"] for item in visible.json()] == ["case-participant"]
            assert client.get("/api/v1/participants/other-participant", headers=worker).status_code == 404
            denied = client.post("/api/v1/cases/", headers=worker, json={"participant_id": "other-participant", "title": "Fuera de zona"})
            assert denied.status_code == 404
            due = (utc_now() - timedelta(minutes=1)).replace(tzinfo=None).isoformat()
            created = client.post("/api/v1/cases/", headers=worker, json={
                "participant_id": "case-participant", "title": "Visita de seguimiento", "assigned_user_id": "case-worker", "due_at": due})
            assert created.status_code == 200, created.text
            case_id = created.json()["id"]
            referred = client.patch(f"/api/v1/cases/{case_id}", headers=worker, json={
                "assigned_user_id": "case-manager", "status": "referred", "note": "Solicito apoyo"})
            assert referred.status_code == 200, referred.text
            events = client.get(f"/api/v1/cases/{case_id}/events", headers=manager)
            assert [item["event_type"] for item in events.json()] == ["created", "referred"]
        with sessions() as db:
            assert db.query(InternalMessage).filter(InternalMessage.recipient_id == "case-manager").count() == 1
            assert db.query(ScheduledTask).filter(ScheduledTask.task_type == "case_reminder", ScheduledTask.status == "active").count() == 1
            result = scheduler_service.run_due_tasks(db)
            assert result == {"processed": 1, "succeeded": 1, "failed": 0}
            assert db.query(InternalMessage).filter(InternalMessage.recipient_id == "case-manager").count() == 2
            assert db.query(ScheduledTask).filter(ScheduledTask.task_type == "case_reminder", ScheduledTask.status == "completed").count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_territory_assignment_is_manager_only():
    engine, _sessions = setup()
    try:
        with TestClient(app) as client:
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            response = client.post("/api/v1/territories/case-project", headers=worker, json={
                "user_id": "case-worker", "department": "Cundinamarca"})
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_child_case_reuses_participant_access_and_tracks_parent():
    engine, _sessions = setup()
    try:
        with TestClient(app) as client:
            manager = auth(client, "case-manager@example.com", "Manager12345!")
            parent = client.post("/api/v1/cases/", headers=manager, json={
                "participant_id": "case-participant", "title": "Hogar de Ana", "case_type": "hogar"})
            assert parent.status_code == 200, parent.text
            child = client.post("/api/v1/cases/", headers=manager, json={
                "participant_id": "other-participant", "title": "Miembro Beto",
                "case_type": "integrante", "parent_case_id": parent.json()["id"]})
            assert child.status_code == 200, child.text
            assert child.json()["parent_case_id"] == parent.json()["id"]
            children = client.get(f"/api/v1/cases/{parent.json()['id']}/children", headers=manager)
            assert [row["id"] for row in children.json()] == [child.json()["id"]]
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            assert client.post("/api/v1/territories/case-project", headers=manager, json={
                "user_id": "case-worker", "department": "Cundinamarca"}).status_code == 200
            assert client.get(f"/api/v1/cases/{parent.json()['id']}/children", headers=worker).json() == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_saved_case_export_uses_existing_scheduler_and_territory_filter():
    engine, sessions = setup()
    try:
        with sessions() as db:
            db.get(Role, "case-worker-role").permissions += ",reports.export"
            db.commit()
        with TestClient(app) as client:
            manager = auth(client, "case-manager@example.com", "Manager12345!")
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            assert client.post("/api/v1/cases/", headers=manager, json={
                "participant_id": "case-participant", "title": "Caso visible"}).status_code == 200
            assert client.post("/api/v1/cases/", headers=manager, json={
                "participant_id": "other-participant", "title": "Caso oculto"}).status_code == 200
            assert client.post("/api/v1/territories/case-project", headers=manager, json={
                "user_id": "case-worker", "department": "Cundinamarca"}).status_code == 200
            created = client.post("/api/v1/saved-exports/case-project", headers=manager, json={
                "name": "Casos por territorio", "export_kind": "cases", "frequency": "weekly",
                "recipient_user_id": "case-worker"})
            assert created.status_code == 200, created.text
            export_id = created.json()["id"]
            assert created.json()["export_kind"] == "cases"
            run = client.post(f"/api/v1/saved-exports/{export_id}/run", headers=worker)
            assert run.status_code == 200, run.text
            downloaded = client.get(f"/api/v1/saved-exports/{export_id}/files/{run.json()['file_id']}", headers=worker)
            assert downloaded.status_code == 200
            assert b"Caso visible" in downloaded.content
            assert b"Caso oculto" not in downloaded.content
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_case_reminder_uses_existing_message_channels(monkeypatch):
    engine, sessions = setup()
    sent = []
    monkeypatch.setattr("app.services.scheduler_service.message_service.send_project_email",
                        lambda *args: (sent.append("email") or "sent", "Correo enviado"))
    class WhatsAppResult:
        status = "sent"
    monkeypatch.setattr("app.services.scheduler_service.whatsapp_service.send_text",
                        lambda *args, **kwargs: (sent.append("whatsapp") or WhatsAppResult()))
    try:
        with sessions() as db:
            user = db.get(User, "case-worker")
            user.phone = "+573001234567"
            db.commit()
        with TestClient(app) as client:
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            due = (utc_now() - timedelta(minutes=1)).replace(tzinfo=None).isoformat()
            response = client.post("/api/v1/cases/", headers=worker, json={
                "participant_id": "case-participant", "title": "Aviso multicanal", "assigned_user_id": "case-worker",
                "due_at": due, "reminder_channels": ["internal", "email", "whatsapp"]})
            assert response.status_code == 200, response.text
        with sessions() as db:
            assert scheduler_service.run_due_tasks(db) == {"processed": 1, "succeeded": 1, "failed": 0}
            assert sent == ["email", "whatsapp"]
            assert db.query(InternalMessage).filter(InternalMessage.recipient_id == "case-worker").count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_territory_blocks_project_wide_report_and_snapshot():
    engine, sessions = setup()
    try:
        with sessions() as db:
            db.get(Role, "case-worker-role").permissions += ",reports.export"
            db.commit()
        with TestClient(app) as client:
            manager = auth(client, "case-manager@example.com", "Manager12345!")
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            assert client.post("/api/v1/territories/case-project", headers=manager, json={
                "user_id": "case-worker", "department": "Cundinamarca", "municipality": "Soacha"}).status_code == 200
            assert client.get("/api/v1/reports/project/case-project/summary", headers=worker).status_code == 403
            denied = client.post("/api/v1/saved-exports/case-project", headers=manager, json={
                "name": "Resumen general", "frequency": "weekly", "recipient_user_id": "case-worker"})
            assert denied.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_saved_export_generates_authorized_snapshot():
    engine, sessions = setup()
    try:
        with TestClient(app) as client:
            manager = auth(client, "case-manager@example.com", "Manager12345!")
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            created = client.post("/api/v1/saved-exports/case-project", headers=manager, json={
                "name": "Resumen semanal", "frequency": "weekly", "recipient_user_id": "case-manager"})
            assert created.status_code == 200, created.text
            export_id = created.json()["id"]
            assert client.get("/api/v1/saved-exports/case-project", headers=worker).status_code == 403
            run = client.post(f"/api/v1/saved-exports/{export_id}/run", headers=manager)
            assert run.status_code == 200, run.text
            file_id = run.json()["file_id"]
            assert client.get(f"/api/v1/saved-exports/{export_id}/files/{file_id}", headers=worker).status_code == 403
            downloaded = client.get(f"/api/v1/saved-exports/{export_id}/files/{file_id}", headers=manager)
            assert downloaded.status_code == 200
            assert downloaded.content.startswith(b"PK")
            with sessions() as db:
                scheduled = db.query(ScheduledTask).filter(ScheduledTask.target_id == export_id).first()
                assert scheduled and scheduled.task_type == "saved_export"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_territorial_user_cannot_search_or_export_other_records():
    engine, sessions = setup()
    try:
        with sessions() as db:
            db.add_all([
                BuilderTemplate(id="case-form", project_id="case-project", name="Visitas"),
                RuntimeRecord(id="visible-record", project_id="case-project", template_id="case-form", participant_id="case-participant"),
                RuntimeRecord(id="hidden-record", project_id="case-project", template_id="case-form", participant_id="other-participant"),
                UserTerritory(project_id="case-project", user_id="case-worker", department="Cundinamarca", municipality="Soacha"),
            ])
            db.commit()
        with TestClient(app) as client:
            worker = auth(client, "case-worker@example.com", "Worker12345!")
            found = client.get("/api/v1/runtime/template/case-form/records/search", headers=worker)
            assert found.status_code == 200, found.text
            assert found.json()["total"] == 1
            assert found.json()["items"][0]["id"] == "visible-record"
            assert client.get("/api/v1/runtime/record/hidden-record", headers=worker).status_code == 404
            exported = client.get("/api/v1/runtime/template/case-form/records/export.csv", headers=worker)
            assert exported.status_code == 200
            assert "visible-record" in exported.text and "hidden-record" not in exported.text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
