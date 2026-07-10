from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    with sessions() as db:
        project = Project(id="msg-project", name="Mensajes")
        other_project = Project(id="msg-other-project", name="Otro")
        sender = User(id="sender", full_name="Sender", document_id="sender-doc", email="sender@example.com", password_hash=hash_password("Sender12345!"))
        recipient = User(id="recipient", full_name="Recipient", document_id="recipient-doc", email="recipient@example.com", password_hash=hash_password("Recipient12345!"))
        outsider = User(id="outsider", full_name="Outsider", document_id="outsider-doc", email="outsider@example.com", password_hash=hash_password("Outsider12345!"))
        db.add_all([
            project,
            other_project,
            sender,
            recipient,
            outsider,
            UserProjectAssignment(user_id=sender.id, project_id=project.id, status="active"),
            UserProjectAssignment(user_id=recipient.id, project_id=project.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=other_project.id, status="active"),
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


def test_internal_message_inbox_sent_counts_and_read_status():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            sender_headers = auth(client, "sender@example.com", "Sender12345!")
            recipient_headers = auth(client, "recipient@example.com", "Recipient12345!")

            create = client.post(
                "/api/v1/messages/internal",
                headers=sender_headers,
                json={
                    "project_id": "msg-project",
                    "recipient_id": "recipient",
                    "subject": "Revision",
                    "body": "Por favor revisar el registro.",
                },
            )
            assert create.status_code == 200
            message = create.json()
            assert message["sender_id"] == "sender"
            assert message["status"] == "unread"

            inbox = client.get("/api/v1/messages/internal/msg-project/inbox", headers=recipient_headers)
            assert inbox.status_code == 200
            assert [item["id"] for item in inbox.json()] == [message["id"]]

            sent = client.get("/api/v1/messages/internal/msg-project/sent", headers=sender_headers)
            assert sent.status_code == 200
            assert [item["id"] for item in sent.json()] == [message["id"]]

            counts = client.get("/api/v1/messages/internal/msg-project/counts", headers=recipient_headers)
            assert counts.status_code == 200
            assert counts.json() == {"unread": 1, "inbox": 1, "sent": 0}

            update = client.patch(
                f"/api/v1/messages/internal/msg-project/{message['id']}",
                headers=recipient_headers,
                json={"status": "read"},
            )
            assert update.status_code == 200
            assert update.json()["status"] == "read"

            counts_after = client.get("/api/v1/messages/internal/msg-project/counts", headers=recipient_headers)
            assert counts_after.json()["unread"] == 0
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_mail_autoconfig_suggests_known_provider_and_ignores_unknown():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            sender_headers = auth(client, "sender@example.com", "Sender12345!")

            known = client.get("/api/v1/messages/profiles/autoconfig", headers=sender_headers, params={"email": "coordinador@gmail.com"})
            assert known.status_code == 200
            assert known.json() == {
                "found": True,
                "sender_email": "coordinador@gmail.com",
                "server_host": "smtp.gmail.com",
                "server_port": "587",
                "use_tls": True,
            }

            unknown = client.get("/api/v1/messages/profiles/autoconfig", headers=sender_headers, params={"email": "coordinador@fundacion-interna.org"})
            assert unknown.status_code == 200
            assert unknown.json()["found"] is False
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_mail_profile_test_send_requires_project_access_and_reports_missing_server():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            sender_headers = auth(client, "sender@example.com", "Sender12345!")
            outsider_headers = auth(client, "outsider@example.com", "Outsider12345!")

            created = client.post(
                "/api/v1/messages/profiles",
                headers=sender_headers,
                json={"project_id": "msg-project", "name": "Notificaciones", "sender_email": "no-reply@fundacion.org"},
            )
            assert created.status_code == 200
            profile_id = created.json()["id"]

            denied = client.post(f"/api/v1/messages/profiles/{profile_id}/test-send", headers=outsider_headers)
            assert denied.status_code == 403

            result = client.post(f"/api/v1/messages/profiles/{profile_id}/test-send", headers=sender_headers)
            assert result.status_code == 200
            assert result.json()["sent"] is False
            assert "servidor SMTP" in result.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_message_recipient_must_belong_to_project():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            sender_headers = auth(client, "sender@example.com", "Sender12345!")
            response = client.post(
                "/api/v1/messages/internal",
                headers=sender_headers,
                json={
                    "project_id": "msg-project",
                    "recipient_id": "outsider",
                    "subject": "No deberia",
                    "body": "Este usuario no pertenece al proyecto.",
                },
            )
            assert response.status_code == 400
            assert "destinatario" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
