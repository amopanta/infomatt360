"""Teams stay separate from import cohorts and grant no implicit form access."""

import json

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.participants import Participant
from test_form_assignments_reopening import auth, setup_client


def test_team_members_and_bulk_form_assignment():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            created = client.post("/api/v1/gestor-teams/project/assign-project", headers=admin, json={"name": "Equipo Soacha"})
            assert created.status_code == 201, created.text
            team_id = created.json()["id"]
            assert client.post("/api/v1/gestor-teams/project/assign-project", headers=admin, json={"name": "equipo soacha"}).status_code == 409
            assert client.get("/api/v1/gestor-teams/project/assign-project", headers=owner).status_code == 403
            invalid = client.put(f"/api/v1/gestor-teams/{team_id}/members", headers=admin,
                json={"user_ids": ["assign-owner"], "participant_ids": ["not-here"]})
            assert invalid.status_code == 422
            saved = client.put(f"/api/v1/gestor-teams/{team_id}/members", headers=admin,
                json={"user_ids": ["assign-owner"], "participant_ids": ["assign-p1", "assign-p2"]})
            assert saved.status_code == 200, saved.text
            assert set(saved.json()["participant_ids"]) == {"assign-p1", "assign-p2"}
            with sessions() as db:
                assert json.loads(db.get(Participant, "assign-p1").metadata_json)["group_name"] == "Soacha"
            assert client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json() == []
            preview = client.post("/api/v1/form-assignments/templates/closed-form/bulk-assign", headers=admin,
                data={"responsible_user_id": "assign-owner", "mode": "team", "team_id": team_id, "preview_only": "true"})
            assert preview.status_code == 200 and preview.json()["to_assign"] == 2, preview.text
            applied = client.post("/api/v1/form-assignments/templates/closed-form/bulk-assign", headers=admin,
                data={"responsible_user_id": "assign-owner", "mode": "team", "team_id": team_id, "preview_only": "false"})
            assert applied.status_code == 200 and applied.json()["applied"] == 2, applied.text
            assert len(client.get("/api/v1/form-assignments/mine/assign-project", headers=owner).json()) == 2
            assert client.delete(f"/api/v1/gestor-teams/{team_id}", headers=admin).status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
