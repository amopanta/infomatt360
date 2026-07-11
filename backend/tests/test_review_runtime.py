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
from app.models.messages import InternalMessage
from app.models.runtime_record import RuntimeRecord


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="review-user", full_name="Reviewer", document_id="review-doc", email="review@example.com", password_hash=hash_password("Reviewer12345!"))
        coordinator = User(id="review-coordinator", full_name="Coordinator", document_id="coordinator-doc", email="coordinator-review@example.com", password_hash=hash_password("Coordinator12345!"))
        approver = User(id="review-approver", full_name="Approver", document_id="approver-doc", email="approver-review@example.com", password_hash=hash_password("Approver12345!"))
        owner = User(id="review-owner", full_name="Owner", document_id="owner-doc", email="owner-review@example.com", password_hash=hash_password("Owner12345!"))
        outsider = User(id="review-outsider", full_name="Outsider", document_id="outsider-doc", email="outsider-review@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="review-project", name="Revision")
        other_project = Project(id="review-other-project", name="Otra revision")
        reviewer_role = Role(id="reviewer-role", name="Revisor", permissions="records.review")
        coordinator_role = Role(id="coordinator-role", name="Coordinador", permissions="records.coordinate")
        approver_role = Role(id="approver-role", name="Aprobador", permissions="records.approve")
        owner_role = Role(id="owner-role", name="Capturista", permissions="records.write")
        outsider_role = Role(id="outsider-role", name="Consulta", permissions="records.read")
        template = BuilderTemplate(id="review-template", project_id=project.id, name="Plantilla", status="published")
        record = RuntimeRecord(id="review-record", project_id=project.id, template_id=template.id, status="submitted", submitted_by=user.id)
        owned_record = RuntimeRecord(id="review-owned-record", project_id=project.id, template_id=template.id, status="submitted", submitted_by=owner.id)
        db.add_all([
            user,
            coordinator,
            approver,
            owner,
            outsider,
            project,
            other_project,
            reviewer_role,
            coordinator_role,
            approver_role,
            owner_role,
            outsider_role,
            template,
            record,
            owned_record,
            UserProjectAssignment(user_id=user.id, project_id=project.id, role_id=reviewer_role.id, status="active"),
            UserProjectAssignment(user_id=coordinator.id, project_id=project.id, role_id=coordinator_role.id, status="active"),
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=owner.id, project_id=project.id, role_id=owner_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=other_project.id, role_id=outsider_role.id, status="active"),
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


def test_review_action_updates_runtime_record_and_lists_history():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "review@example.com", "Reviewer12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "under_review",
                    "action": "start_review",
                    "notes": "Inicio de revision.",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["from_status"] == "submitted"
            assert data["to_status"] == "under_review"
            assert data["created_at"]

            with sessions() as db:
                record = db.get(RuntimeRecord, "review-record")
                assert record is not None
                assert record.status == "under_review"

            history = client.get("/api/v1/review/records/review-record/actions", headers=headers)
            assert history.status_code == 200
            assert [item["action"] for item in history.json()] == ["start_review"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_review_rejects_invalid_transition_and_cross_project_access():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "review@example.com", "Reviewer12345!")
            invalid = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "draft",
                    "action": "rewind",
                },
            )
            assert invalid.status_code == 400
            assert "transicion" in invalid.json()["detail"].lower()

            outsider_headers = auth(client, "outsider-review@example.com", "Outsider12345!")
            forbidden = client.get("/api/v1/review/records/review-record/actions", headers=outsider_headers)
            assert forbidden.status_code == 403

            wrong_project = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={
                    "project_id": "review-other-project",
                    "record_id": "review-record",
                    "to_status": "under_review",
                    "action": "start_review",
                },
            )
            assert wrong_project.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_review_approve_requires_approval_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            reviewer_headers = auth(client, "review@example.com", "Reviewer12345!")
            reviewer_response = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "approved",
                    "action": "approve",
                    "notes": "Intento sin permiso de aprobacion.",
                },
            )
            assert reviewer_response.status_code == 403
            assert "permiso" in reviewer_response.json()["detail"].lower()

            owner_headers = auth(client, "owner-review@example.com", "Owner12345!")
            owner_response = client.post(
                "/api/v1/review/actions",
                headers=owner_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-owned-record",
                    "to_status": "approved",
                    "action": "approve",
                },
            )
            assert owner_response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_review_supports_multi_level_approval_permissions():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            reviewer_headers = auth(client, "review@example.com", "Reviewer12345!")
            coordinator_headers = auth(client, "coordinator-review@example.com", "Coordinator12345!")
            approver_headers = auth(client, "approver-review@example.com", "Approver12345!")

            start = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "under_review",
                    "action": "start_review",
                },
            )
            assert start.status_code == 200

            technical = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "tech_approved",
                    "action": "technical_approve",
                },
            )
            assert technical.status_code == 200

            coordinator_forbidden = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "coordinator_approved",
                    "action": "coordinator_approve",
                },
            )
            assert coordinator_forbidden.status_code == 403

            coordinator = client.post(
                "/api/v1/review/actions",
                headers=coordinator_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "coordinator_approved",
                    "action": "coordinator_approve",
                },
            )
            assert coordinator.status_code == 200

            approved = client.post(
                "/api/v1/review/actions",
                headers=approver_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-record",
                    "to_status": "approved",
                    "action": "final_approve",
                },
            )
            assert approved.status_code == 200

            with sessions() as db:
                record = db.get(RuntimeRecord, "review-record")
                assert record is not None
                assert record.status == "approved"

            history = client.get("/api/v1/review/records/review-record/actions", headers=approver_headers)
            assert history.status_code == 200
            assert [item["to_status"] for item in history.json()] == [
                "approved",
                "coordinator_approved",
                "tech_approved",
                "under_review",
            ]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_review_action_notifies_record_owner_when_reviewer_changes_status():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            reviewer_headers = auth(client, "review@example.com", "Reviewer12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "review-project",
                    "record_id": "review-owned-record",
                    "to_status": "returned",
                    "action": "return",
                    "notes": "Falta soporte documental.",
                },
            )
            assert response.status_code == 200

            with sessions() as db:
                messages = db.query(InternalMessage).filter(
                    InternalMessage.project_id == "review-project",
                    InternalMessage.recipient_id == "review-owner",
                ).all()
                assert len(messages) == 1
                assert messages[0].sender_id == "review-user"
                assert messages[0].status == "unread"
                assert "review-owned-record" in messages[0].body
                assert "Falta soporte documental" in messages[0].body

            owner_headers = auth(client, "owner-review@example.com", "Owner12345!")
            inbox = client.get("/api/v1/messages/internal/review-project/inbox", headers=owner_headers)
            assert inbox.status_code == 200
            assert inbox.json()[0]["subject"] == "Registro returned"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
