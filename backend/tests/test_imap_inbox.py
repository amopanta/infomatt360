import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.services.imap_service as imap_module
from app.core.security import decrypt_text, encrypt_text, hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Role, User
from app.models.messages import ExternalMailMessage, MailProfile
from app.models.scheduler import ScheduledTask, TaskRun
from app.services import imap_service
from app.services.scheduler_service import scheduler_service


class FakeMailMessage:
    def __init__(self, uid, subject="Asunto", from_="remitente@externo.test", text="Cuerpo del mensaje", date=None):
        self.uid = uid
        self.subject = subject
        self.from_ = from_
        self.text = text
        self.html = None
        self.date = date or datetime.now(timezone.utc)


class FakeMailBox:
    pending_messages: list = []
    last_instance = None

    def __init__(self, host, port=None):
        self.host = host
        self.port = port
        self.fetch_criteria = None

    def login(self, username, password, initial_folder=None):
        self.username = username
        self.password = password
        self.initial_folder = initial_folder
        FakeMailBox.last_instance = self
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def fetch(self, criteria, mark_seen=False):
        self.fetch_criteria = criteria
        for msg in FakeMailBox.pending_messages:
            yield msg


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        mail_role = Role(id="imap-mail-role", name="Correo", permissions="records.read")
        member = User(id="imap-member", full_name="Member", document_id="imap-member-doc", email="imap-member@example.com", password_hash=hash_password("Member12345!"))
        outsider = User(id="imap-outsider", full_name="Outsider", document_id="imap-outsider-doc", email="imap-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        db.add_all([
            mail_role,
            member,
            outsider,
            UserProjectAssignment(user_id=member.id, project_id="imap-project", role_id=mail_role.id, status="active"),
            UserProjectAssignment(user_id=member.id, project_id="imap-project-2", role_id=mail_role.id, status="active"),
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


def _make_profile(db, last_imap_uid=None):
    profile = MailProfile(
        project_id="imap-project",
        name="Buzon externo",
        provider="imap",
        sender_email="buzon@externo.test",
        server_host="imap.externo.test",
        server_port="993",
        config_json=encrypt_text(json.dumps({"username": "buzon@externo.test", "password": "secreto"})),
        is_default="false",
        status="active",
        last_imap_uid=last_imap_uid,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.fixture(autouse=True)
def _reset_fake_mailbox(monkeypatch):
    FakeMailBox.pending_messages = []
    FakeMailBox.last_instance = None
    monkeypatch.setattr(imap_module, "MailBox", FakeMailBox)
    yield


def test_first_poll_without_watermark_fetches_all_messages():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db)
            profile_id = profile.id

        FakeMailBox.pending_messages = [FakeMailMessage(uid=1), FakeMailMessage(uid=2), FakeMailMessage(uid=3)]

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            status_value, result_text = imap_service.poll_profile(db, profile)
            assert status_value == "success"
            assert "3 mensaje(s) nuevo(s)" in result_text
            assert FakeMailBox.last_instance.fetch_criteria == "ALL"

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            assert profile.last_imap_uid == 3
            rows = db.query(ExternalMailMessage).filter(ExternalMailMessage.mail_profile_id == profile_id).all()
            assert {row.uid for row in rows} == {1, 2, 3}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_incremental_poll_only_fetches_new_uids_and_reflects_watermark():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db, last_imap_uid=3)
            profile_id = profile.id

        FakeMailBox.pending_messages = [FakeMailMessage(uid=4), FakeMailMessage(uid=5)]

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            status_value, result_text = imap_service.poll_profile(db, profile)
            assert status_value == "success"
            assert "2 mensaje(s) nuevo(s)" in result_text
            assert FakeMailBox.last_instance.fetch_criteria == "(UID 4:*)"

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            assert profile.last_imap_uid == 5
            rows = db.query(ExternalMailMessage).filter(ExternalMailMessage.mail_profile_id == profile_id).all()
            assert {row.uid for row in rows} == {4, 5}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_malformed_message_is_skipped_without_aborting_the_batch():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db)
            profile_id = profile.id

        FakeMailBox.pending_messages = [
            FakeMailMessage(uid=1),
            FakeMailMessage(uid="no-numerico"),
            FakeMailMessage(uid=2),
        ]

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            status_value, result_text = imap_service.poll_profile(db, profile)
            assert status_value == "success"
            assert "2 mensaje(s) nuevo(s), 1 omitido(s)" in result_text

        with sessions() as db:
            rows = db.query(ExternalMailMessage).filter(ExternalMailMessage.mail_profile_id == profile_id).all()
            assert {row.uid for row in rows} == {1, 2}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_duplicate_uid_under_unique_constraint_is_skipped_not_fatal():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db)
            profile_id = profile.id
            db.add(ExternalMailMessage(
                project_id="imap-project", mail_profile_id=profile_id, uid=1,
                from_address="ya@existe.test", subject="Ya existente", body="...",
                fetched_at=utc_now(), status="unread",
            ))
            db.commit()

        FakeMailBox.pending_messages = [FakeMailMessage(uid=1), FakeMailMessage(uid=2)]

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            status_value, result_text = imap_service.poll_profile(db, profile)
            assert status_value == "success"
            assert "1 mensaje(s) nuevo(s), 1 omitido(s)" in result_text

        with sessions() as db:
            rows = db.query(ExternalMailMessage).filter(ExternalMailMessage.mail_profile_id == profile_id).all()
            assert len(rows) == 2
            assert {row.uid for row in rows} == {1, 2}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_external_inbox_routes_scoping_and_status_update():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db)
            db.add(ExternalMailMessage(
                project_id="imap-project", mail_profile_id=profile.id, uid=1,
                from_address="remitente@externo.test", subject="Hola", body="Cuerpo",
                fetched_at=utc_now(), status="unread",
            ))
            db.commit()
            message_id = db.query(ExternalMailMessage).filter(ExternalMailMessage.mail_profile_id == profile.id).one().id

        with TestClient(app) as client:
            outsider_headers = auth(client, "imap-outsider@example.com", "Outsider12345!")
            denied = client.get("/api/v1/messages/external/imap-project/inbox", headers=outsider_headers)
            assert denied.status_code == 403

            member_headers = auth(client, "imap-member@example.com", "Member12345!")
            other_project_update = client.patch(
                "/api/v1/messages/external/imap-project-2/" + message_id,
                json={"status": "read"},
                headers=member_headers,
            )
            assert other_project_update.status_code == 404

            listed = client.get("/api/v1/messages/external/imap-project/inbox", headers=member_headers)
            assert listed.status_code == 200
            assert len(listed.json()) == 1
            assert listed.json()[0]["from_address"] == "remitente@externo.test"

            updated = client.patch(
                "/api/v1/messages/external/imap-project/" + message_id,
                json={"status": "read"},
                headers=member_headers,
            )
            assert updated.status_code == 200
            assert updated.json()["status"] == "read"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_scheduler_wiring_dispatches_mail_poll_task_type(monkeypatch):
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            profile = _make_profile(db)
            task = ScheduledTask(
                project_id="imap-project", name="Sondeo IMAP", task_type="mail_poll",
                target_id=profile.id, frequency="hourly", status="active",
                next_run_at=utc_now() - timedelta(minutes=5),
            )
            db.add(task)
            db.commit()
            task_id = task.id

        monkeypatch.setattr(imap_service, "poll_profile", lambda db, profile: ("success", "2 mensaje(s) nuevo(s), 0 omitido(s)"))

        with sessions() as db:
            result = scheduler_service.run_due_tasks(db, limit=10)
            assert result == {"processed": 1, "succeeded": 1, "failed": 0}

        with sessions() as db:
            refreshed = db.get(ScheduledTask, task_id)
            assert refreshed.last_result == "2 mensaje(s) nuevo(s), 0 omitido(s)"
            runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
            assert len(runs) == 1
            assert runs[0].status == "success"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_mail_profile_config_json_is_encrypted_at_rest_and_hidden_in_responses():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            member_headers = auth(client, "imap-member@example.com", "Member12345!")
            created = client.post(
                "/api/v1/messages/profiles",
                json={
                    "project_id": "imap-project",
                    "name": "Buzon externo",
                    "provider": "imap",
                    "sender_email": "buzon@externo.test",
                    "server_host": "imap.externo.test",
                    "server_port": "993",
                    "config_json": json.dumps({"username": "buzon@externo.test", "password": "secreto"}),
                },
                headers=member_headers,
            )
            assert created.status_code == 200
            body = created.json()
            assert "config_json" not in body
            profile_id = body["id"]

            listed = client.get("/api/v1/messages/profiles/imap-project", headers=member_headers)
            assert listed.status_code == 200
            assert all("config_json" not in item for item in listed.json())

        with sessions() as db:
            profile = db.get(MailProfile, profile_id)
            stored = json.loads(decrypt_text(profile.config_json))
            assert stored["password"] == "secreto"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
