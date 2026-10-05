"""Administrator removal hides a form while retaining submitted evidence."""

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.builder import BuilderTemplate
from test_form_assignments_reopening import auth, setup_client


def test_admin_delete_requires_name_and_preserves_records():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            assigned = client.post("/api/v1/form-assignments/templates/closed-form", headers=admin,
                json={"participant_id": "assign-p1", "responsible_user_id": "assign-owner"})
            assert assigned.status_code == 200, assigned.text
            saved = client.post("/api/v1/runtime/save", headers=owner,
                json={"project_id": "assign-project", "template_id": "closed-form", "participant_id": "assign-p1",
                      "values": [{"field_name": "answer", "field_value_json": '"historical"'}]})
            assert saved.status_code == 200, saved.text
            record_id = saved.json()["id"]
            endpoint = "/api/v1/builder/templates/detail/closed-form/delete"
            assert client.post(endpoint, headers=owner, json={"name": "Visita cerrada"}).status_code == 403
            assert client.post(endpoint, headers=admin, json={"name": "Incorrecto"}).status_code == 422
            deleted = client.post(endpoint, headers=admin, json={"name": "Visita cerrada"})
            assert deleted.status_code == 200 and deleted.json()["deleted"] is True, deleted.text
            assert client.get("/api/v1/builder/templates/detail/closed-form", headers=admin).status_code == 404
            assert "closed-form" not in [row["id"] for row in client.get("/api/v1/builder/templates/assign-project", headers=admin).json()]
            assert client.get("/api/v1/runtime/template/closed-form", headers=owner).status_code == 404
            assert client.get(f"/api/v1/runtime/record/{record_id}", headers=admin).status_code == 200
            assert client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json() == []
            with sessions() as db:
                assert db.get(BuilderTemplate, "closed-form").status == "deleted"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
