"""End-to-end access, capture and controlled reopening for assigned forms."""

import json
from io import BytesIO

from openpyxl import Workbook

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.schemas.builder import ParticipantSource


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="assign-project", name="Asignaciones")
        closed = BuilderTemplate(id="closed-form", project_id=project.id, name="Visita cerrada", status="published",
            participant_source_json=ParticipantSource(access_mode="closed", participant_key_field="document_id").model_dump_json())
        opened = BuilderTemplate(id="open-form", project_id=project.id, name="Visita abierta", status="published",
            participant_source_json=ParticipantSource(access_mode="open", participant_key_field="document_id").model_dump_json())
        roles = [
            Role(id="assign-admin-role", name="Administrador", permissions="identity.users.manage,builder.write,records.read,records.write,records.approve,records.review,participants.create"),
            Role(id="assign-owner-role", name="Responsable", permissions="records.read,records.write,participants.create"),
            Role(id="assign-other-role", name="Otro", permissions="records.read,records.write"),
        ]
        users = [
            User(id="assign-admin", full_name="Admin", document_id="assign-admin-doc", email="assign-admin@example.com", password_hash=hash_password("Admin12345!")),
            User(id="assign-owner", full_name="Responsable", document_id="assign-owner-doc", email="assign-owner@example.com", password_hash=hash_password("Owner12345!")),
            User(id="assign-other", full_name="Otro", document_id="assign-other-doc", email="assign-other@example.com", password_hash=hash_password("Other12345!")),
        ]
        db.add_all([project, closed, opened, *roles, *users,
            Participant(id="assign-p1", project_id=project.id, full_name="Primera", document_id="1001", metadata_json=json.dumps({"group_name": "Soacha"})),
            Participant(id="assign-p2", project_id=project.id, full_name="Segunda", document_id="1002", metadata_json=json.dumps({"group_name": "Soacha"})),
            *[UserProjectAssignment(user_id=user.id, project_id=project.id, role_id=role.id, status="active") for user, role in zip(users, roles)],
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_closed_form_assignment_capture_visibility_and_reopening():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            other = auth(client, "assign-other@example.com", "Other12345!")
            for participant_id, responsible_user_id in (("assign-p1", "assign-owner"), ("assign-p2", "assign-other")):
                response = client.post("/api/v1/form-assignments/templates/closed-form", headers=admin,
                    json={"participant_id": participant_id, "responsible_user_id": responsible_user_id})
                assert response.status_code == 200, response.text
            mine = client.get("/api/v1/form-assignments/mine/assign-project", headers=owner)
            assert mine.status_code == 200, mine.text
            assert [(item["template_name"], item["participant_name"], item["document_id"]) for item in mine.json()] == [("Visita cerrada", "Primera", "1001")]
            assert [item["participant_id"] for item in client.get("/api/v1/form-assignments/mine/assign-project", headers=other).json()] == ["assign-p2"]
            assert client.get("/api/v1/form-assignments/mine/another-project", headers=owner).status_code == 403
            eligible = client.get("/api/v1/builder/templates/detail/closed-form/eligible-participants", headers=owner)
            assert [row["id"] for row in eligible.json()] == ["assign-p1"]
            unauthorized = client.post("/api/v1/runtime/save", headers=owner,
                json={"project_id": "assign-project", "template_id": "closed-form", "participant_id": "assign-p2", "values": []})
            assert unauthorized.status_code == 422
            started = client.post("/api/v1/form-assignments/templates/closed-form/assign-p1/start", headers=owner)
            assert started.status_code == 200 and started.json()["status"] == "in_progress"
            saved = client.post("/api/v1/runtime/save", headers=owner,
                json={"project_id": "assign-project", "template_id": "closed-form", "participant_id": "assign-p1",
                      "values": [{"field_name": "respuesta", "field_value_json": '"Antes"'}]})
            assert saved.status_code == 200, saved.text
            record_id = saved.json()["id"]
            repeated = client.post("/api/v1/form-assignments/templates/closed-form/assign-p1/start", headers=owner)
            assert repeated.status_code == 409
            assert "ya tiene un registro asociado" in repeated.json()["detail"]
            listed = client.get("/api/v1/form-assignments/templates/closed-form", headers=owner)
            assert listed.status_code == 200, listed.text
            assert [(row["document_id"], row["status"], row["record_id"]) for row in listed.json()] == [("1001", "completed", record_id)]
            assert client.get(f"/api/v1/runtime/record/{record_id}", headers=other).status_code == 404
            assert client.get(f"/api/v1/runtime/record/{record_id}", headers=owner).status_code == 200
            assert client.post(f"/api/v1/runtime/record/{record_id}/duplicate", headers=owner).status_code == 409
            assert client.get("/api/v1/runtime/template/closed-form/records/search", headers=other).json()["total"] == 0
            assert client.get("/api/v1/participants/assign-p1/activities", headers=owner).json()[0]["assignment_status"] == "completed"
            approved = client.post("/api/v1/review/actions", headers=admin,
                json={"project_id": "assign-project", "record_id": record_id, "to_status": "approved", "action": "approve"})
            assert approved.status_code == 200, approved.text
            assert client.get("/api/v1/participants/assign-p1/activities", headers=owner).json()[0]["assignment_status"] == "closed"
            closed_list = client.get("/api/v1/form-assignments/templates/closed-form", headers=owner).json()
            assert closed_list[0]["status"] == "closed" and closed_list[0]["record_id"] == record_id
            correction = {"field_name": "respuesta", "field_value_json": '"Después"', "expected_lock_version": 1}
            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=owner, json=correction).status_code == 400
            assert client.post(f"/api/v1/review/records/{record_id}/reopen", headers=owner,
                json={"reason": "Corregir dato"}).status_code == 403
            assert client.post("/api/v1/review/actions", headers=admin,
                json={"project_id": "assign-project", "record_id": record_id, "to_status": "returned", "action": "return", "notes": "Otro camino"}).status_code == 400
            reopened = client.post(f"/api/v1/review/records/{record_id}/reopen", headers=admin,
                json={"reason": "Corregir documento revisado"})
            assert reopened.status_code == 200, reopened.text
            assert reopened.json()["from_status"] == "approved"
            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=other, json=correction).status_code == 404
            corrected = client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=owner, json=correction)
            assert corrected.status_code == 200, corrected.text
            for to_status in ("corrected", "submitted"):
                response = client.post("/api/v1/review/actions", headers=owner,
                    json={"project_id": "assign-project", "record_id": record_id, "to_status": to_status, "action": to_status})
                assert response.status_code == 200, response.text
            again = client.post("/api/v1/review/actions", headers=admin,
                json={"project_id": "assign-project", "record_id": record_id, "to_status": "approved", "action": "approve"})
            assert again.status_code == 200, again.text
            history = client.get(f"/api/v1/review/records/{record_id}/actions", headers=admin).json()
            assert len([row for row in history if row["to_status"] == "approved"]) == 2
            with sessions() as db:
                edits = db.query(AuditLog).filter_by(entity_id=record_id, action="edit_field").all()
                assert len(edits) == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_group_and_excel_bulk_assignment_preview_and_apply():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            path = "/api/v1/form-assignments/templates/closed-form/bulk-assign"
            group = {"responsible_user_id": "assign-owner", "mode": "group", "group_name": "Soacha"}
            assert client.post(path, headers=owner, data=group).status_code == 403
            preview = client.post(path, headers=admin, data=group)
            assert preview.status_code == 200, preview.text
            assert (preview.json()["selected"], preview.json()["to_assign"], preview.json()["applied"]) == (2, 2, 0)
            assert client.get("/api/v1/form-assignments/templates/closed-form", headers=admin).json() == []
            applied = client.post(path, headers=admin, data={**group, "preview_only": "false"})
            assert applied.status_code == 200, applied.text
            assert applied.json()["applied"] == 2
            assert len(client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json()) == 2
            assert client.post(path, headers=admin, data=group).json()["already_assigned"] == 2

            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["documento"])
            sheet.append(["1001"])
            sheet.append(["desconocido"])
            output = BytesIO()
            workbook.save(output)
            excel = {"responsible_user_id": "assign-other", "mode": "excel", "preview_only": "false"}
            invalid = client.post(path, headers=admin, data=excel, files={"upload": ("asignacion.xlsx", output.getvalue())})
            assert invalid.status_code == 200, invalid.text
            assert invalid.json()["applied"] == 0 and invalid.json()["issues"]
            assert len(client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json()) == 2

            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["documento"])
            sheet.append(["1001"])
            output = BytesIO()
            workbook.save(output)
            valid = client.post(path, headers=admin, data=excel, files={"upload": ("asignacion.xlsx", output.getvalue())})
            assert valid.status_code == 200, valid.text
            assert (valid.json()["to_reassign"], valid.json()["applied"]) == (1, 1)
            assert [item["participant_id"] for item in client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json()] == ["assign-p2"]
            other = auth(client, "assign-other@example.com", "Other12345!")
            saved = client.post("/api/v1/runtime/save", headers=other, json={
                "project_id": "assign-project", "template_id": "closed-form", "participant_id": "assign-p1", "values": [],
            })
            assert saved.status_code == 200, saved.text
            protected = client.post(path, headers=admin, data=group).json()
            assert (protected["protected"], protected["already_assigned"], protected["to_reassign"]) == (1, 1, 0)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_open_form_new_participant_requires_permission_and_closed_form_rejects_it():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            other = auth(client, "assign-other@example.com", "Other12345!")
            payload = {"full_name": "Nueva persona", "document_id": "3003", "municipality": "Soacha"}
            assert client.post("/api/v1/form-assignments/templates/open-form/participants", headers=other, json=payload).status_code == 403
            assert client.post("/api/v1/form-assignments/templates/closed-form/participants", headers=owner, json=payload).status_code == 403
            created = client.post("/api/v1/form-assignments/templates/open-form/participants", headers=owner, json=payload)
            assert created.status_code == 200, created.text
            participant_id = created.json()["participant_id"]
            eligible = client.get("/api/v1/builder/templates/detail/open-form/eligible-participants", headers=owner).json()
            assert [(row["id"], row["municipality"]) for row in eligible] == [(participant_id, "Soacha")]
            assert client.get("/api/v1/builder/templates/detail/open-form/eligible-participants", headers=other).json() == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_assigned_responsible_can_correct_phone_before_submission_with_audit():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            other = auth(client, "assign-other@example.com", "Other12345!")
            assigned = client.post("/api/v1/form-assignments/templates/closed-form", headers=admin,
                json={"participant_id": "assign-p1", "responsible_user_id": "assign-owner"})
            assert assigned.status_code == 200, assigned.text
            path = "/api/v1/form-assignments/templates/closed-form/assign-p1/phone"
            assert client.patch(path, headers=other, json={"phone": "3001234567"}).status_code == 404
            assert client.patch(path, headers=owner, json={"phone": "123"}).status_code == 422
            changed = client.patch(path, headers=owner, json={"phone": "3001234567"})
            assert changed.status_code == 200, changed.text
            assert json.loads(changed.json()["metadata_json"])["phone"] == "3001234567"
            with sessions() as db:
                audit = db.query(AuditLog).filter_by(entity_id="assign-p1", action="update_phone_from_form").one()
                assert json.loads(audit.after_json)["phone"] == "3001234567"
            saved = client.post("/api/v1/runtime/save", headers=owner,
                json={"project_id": "assign-project", "template_id": "closed-form", "participant_id": "assign-p1", "values": []})
            assert saved.status_code == 200, saved.text
            assert client.patch(path, headers=owner, json={"phone": "3007654321"}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
