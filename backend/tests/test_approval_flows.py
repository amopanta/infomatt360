from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.approval_flow import ApprovalFlow, ApprovalFlowStep
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord
from app.services.approval_flow_service import approval_flow_service


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="flow-project", name="Flujos")
        template = BuilderTemplate(id="flow-template", project_id=project.id, name="Formulario", status="published")
        admin_role = Role(id="flow-admin-role", name="Admin", permissions="records.approve,records.review,records.legal")
        legal_role = Role(id="flow-legal-role", name="Juridico", permissions="records.legal")
        reviewer_role = Role(id="flow-review-role", name="Revisor", permissions="records.review")
        admin = User(id="flow-admin", full_name="Admin", document_id="flow-admin-doc", email="flow-admin@example.com", password_hash=hash_password("Admin12345!"))
        legal = User(id="flow-legal", full_name="Legal", document_id="flow-legal-doc", email="flow-legal@example.com", password_hash=hash_password("Legal12345!"))
        legal_2 = User(id="flow-legal-2", full_name="Legal Dos", document_id="flow-legal-2-doc", email="flow-legal-2@example.com", password_hash=hash_password("Legal12345!"))
        reviewer = User(id="flow-reviewer", full_name="Reviewer", document_id="flow-reviewer-doc", email="flow-reviewer@example.com", password_hash=hash_password("Reviewer12345!"))
        record = RuntimeRecord(id="flow-record", project_id=project.id, template_id=template.id, status="submitted", submitted_by=reviewer.id)
        db.add_all([
            project,
            template,
            admin_role,
            legal_role,
            reviewer_role,
            admin,
            legal,
            legal_2,
            reviewer,
            record,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=legal.id, project_id=project.id, role_id=legal_role.id, status="active"),
            UserProjectAssignment(user_id=legal_2.id, project_id=project.id, role_id=legal_role.id, status="active"),
            UserProjectAssignment(user_id=reviewer.id, project_id=project.id, role_id=reviewer_role.id, status="active"),
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


def test_configurable_approval_flow_drives_next_actions_and_permissions():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "flow-admin@example.com", "Admin12345!")
            legal_headers = auth(client, "flow-legal@example.com", "Legal12345!")
            legal_2_headers = auth(client, "flow-legal-2@example.com", "Legal12345!")
            reviewer_headers = auth(client, "flow-reviewer@example.com", "Reviewer12345!")

            create_flow = client.post(
                "/api/v1/approval-flows/",
                headers=admin_headers,
                json={
                    "project_id": "flow-project",
                    "template_id": "flow-template",
                    "name": "Flujo juridico",
                    "description": "Revision juridica antes de aprobacion final.",
                },
            )
            assert create_flow.status_code == 200
            flow = create_flow.json()
            assert flow["flow_version"] == 1

            step = client.post(
                "/api/v1/approval-flows/steps",
                headers=admin_headers,
                json={
                    "flow_id": flow["id"],
                    "step_order": 1,
                    "name": "Juridico",
                    "action_label": "Aprobar jurídico",
                    "action": "legal_approve",
                    "status_after": "legal_approved",
                    "required_permission": "records.legal",
                    "approver_role_id": "flow-legal-role",
                    "require_all": True,
                },
            )
            assert step.status_code == 200
            step_id = step.json()["id"]

            with sessions() as db:
                snapshot_flow_id, snapshot_version, snapshot_json = approval_flow_service.snapshot_for_record(db, "flow-project", "flow-template")
                record = db.get(RuntimeRecord, "flow-record")
                assert record is not None
                record.approval_flow_id = snapshot_flow_id
                record.approval_flow_version = snapshot_version
                record.approval_flow_snapshot_json = snapshot_json
                db.commit()

            update_flow = client.patch(
                f"/api/v1/approval-flows/{flow['id']}",
                headers=admin_headers,
                json={"name": "Flujo juridico actualizado", "status": "active"},
            )
            assert update_flow.status_code == 200
            assert update_flow.json()["name"] == "Flujo juridico actualizado"
            assert update_flow.json()["flow_version"] == 2

            deactivate_step = client.patch(
                f"/api/v1/approval-flows/steps/{step_id}",
                headers=admin_headers,
                json={"status": "inactive"},
            )
            assert deactivate_step.status_code == 200
            assert deactivate_step.json()["status"] == "inactive"

            default_actions = client.get("/api/v1/review/records/flow-record/next-actions", headers=reviewer_headers)
            assert default_actions.status_code == 200
            assert default_actions.json()[0]["source"] == "configured"
            assert default_actions.json()[0]["label"] == "Aprobar jurídico"
            comparison = client.get("/api/v1/review/records/flow-record/flow-comparison", headers=reviewer_headers)
            assert comparison.status_code == 200
            assert comparison.json()["has_snapshot"] is True
            assert comparison.json()["changed"] is True
            assert comparison.json()["snapshot"]["flow_version"] == "1"
            assert comparison.json()["current"]["flow_version"] == "3"
            assert comparison.json()["differences"]
            assert any("versión" in item or "Paso" in item for item in comparison.json()["differences"])

            reactivate_step = client.patch(
                f"/api/v1/approval-flows/steps/{step_id}",
                headers=admin_headers,
                json={"status": "active"},
            )
            assert reactivate_step.status_code == 200
            assert reactivate_step.json()["status"] == "active"
            flow_detail = client.get(f"/api/v1/approval-flows/detail/{flow['id']}", headers=admin_headers)
            assert flow_detail.status_code == 200
            assert flow_detail.json()["flow_version"] == 4

            next_actions = client.get("/api/v1/review/records/flow-record/next-actions", headers=reviewer_headers)
            assert next_actions.status_code == 200
            assert next_actions.json() == [{
                "label": "Aprobar jurídico",
                "to_status": "legal_approved",
                "action": "legal_approve",
                "required_permission": "records.legal",
                "source": "configured",
            }]

            initial_progress = client.get("/api/v1/review/records/flow-record/approval-progress", headers=reviewer_headers)
            assert initial_progress.status_code == 200
            assert initial_progress.json()[0]["required_count"] == 2
            assert initial_progress.json()[0]["approved_count"] == 0
            assert initial_progress.json()[0]["pending_count"] == 2

            forbidden = client.post(
                "/api/v1/review/actions",
                headers=reviewer_headers,
                json={
                    "project_id": "flow-project",
                    "record_id": "flow-record",
                    "to_status": "legal_approved",
                    "action": "legal_approve",
                },
            )
            assert forbidden.status_code == 403

            first_approval = client.post(
                "/api/v1/review/actions",
                headers=legal_headers,
                json={
                    "project_id": "flow-project",
                    "record_id": "flow-record",
                    "to_status": "legal_approved",
                    "action": "legal_approve",
                    "notes": "Cumple revision juridica.",
                },
            )
            assert first_approval.status_code == 200
            assert first_approval.json()["to_status"] == "legal_approved"
            assert first_approval.json()["approval_flow_id"] == flow["id"]
            assert first_approval.json()["approval_flow_version"] == 1

            with sessions() as db:
                record = db.get(RuntimeRecord, "flow-record")
                assert record is not None
                assert record.status == "submitted"

            partial_progress = client.get("/api/v1/review/records/flow-record/approval-progress", headers=reviewer_headers)
            assert partial_progress.status_code == 200
            assert partial_progress.json()[0]["required_count"] == 2
            assert partial_progress.json()[0]["approved_count"] == 1
            assert partial_progress.json()[0]["pending_count"] == 1

            duplicate = client.post(
                "/api/v1/review/actions",
                headers=legal_headers,
                json={
                    "project_id": "flow-project",
                    "record_id": "flow-record",
                    "to_status": "legal_approved",
                    "action": "legal_approve",
                },
            )
            assert duplicate.status_code == 400

            final_approval = client.post(
                "/api/v1/review/actions",
                headers=legal_2_headers,
                json={
                    "project_id": "flow-project",
                    "record_id": "flow-record",
                    "to_status": "legal_approved",
                    "action": "legal_approve",
                    "notes": "Segunda aprobacion juridica.",
                },
            )
            assert final_approval.status_code == 200

            with sessions() as db:
                assert db.query(ApprovalFlow).count() == 1
                assert db.query(ApprovalFlowStep).count() == 1
                assert db.query(RuntimeRecord).count() == 1
                record = db.get(RuntimeRecord, "flow-record")
                assert record is not None
                assert record.status == "legal_approved"

            completed_progress = client.get("/api/v1/review/records/flow-record/approval-progress", headers=reviewer_headers)
            assert completed_progress.status_code == 200
            assert completed_progress.json() == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
