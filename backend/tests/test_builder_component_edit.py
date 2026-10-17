"""Deleting and reordering questions from the form builder."""

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.builder_layout import BuilderColumn, BuilderRow
from app.models.runtime_record import RuntimeRecord
from test_form_assignments_reopening import auth, setup_client


def _build_form(client: TestClient, headers: dict[str, str], template_id: str, names: list[str]) -> list[str]:
    page = client.post("/api/v1/builder/pages", headers=headers, json={"template_id": template_id, "title": "Pagina", "sort_order": 1})
    assert page.status_code == 200, page.text
    section = client.post("/api/v1/builder/sections", headers=headers, json={"page_id": page.json()["id"], "title": "General", "sort_order": 1})
    assert section.status_code == 200, section.text
    ids = []
    for order, name in enumerate(names, start=1):
        row = client.post("/api/v1/builder/rows", headers=headers, json={"section_id": section.json()["id"], "sort_order": order})
        column = client.post("/api/v1/builder/columns", headers=headers, json={"row_id": row.json()["id"], "desktop_width": 12, "sort_order": 1})
        component = client.post("/api/v1/builder/components", headers=headers, json={
            "template_id": template_id, "column_id": column.json()["id"], "component_type": "TEXT", "name": name, "label": name, "sort_order": order,
        })
        assert component.status_code == 200, component.text
        ids.append(component.json()["id"])
    return ids


def _runtime_names(client: TestClient, headers: dict[str, str], template_id: str) -> list[str]:
    runtime = client.get(f"/api/v1/runtime/template/{template_id}", headers=headers)
    assert runtime.status_code == 200, runtime.text
    return [component["name"] for page in runtime.json()["pages"] for section in page["sections"]
            for row in section["rows"] for column in row["columns"] for component in column["components"]]


def test_delete_question_removes_empty_layout_until_form_has_answers():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            owner = auth(client, "assign-owner@example.com", "Owner12345!")
            first, second = _build_form(client, admin, "open-form", ["nombre", "edad"])

            assert client.delete(f"/api/v1/builder/components/detail/{first}", headers=owner).status_code == 403
            deleted = client.delete(f"/api/v1/builder/components/detail/{first}", headers=admin)
            assert deleted.status_code == 200, deleted.text
            assert _runtime_names(client, admin, "open-form") == ["edad"]
            with sessions() as db:
                assert db.query(BuilderRow).count() == 1
                assert db.query(BuilderColumn).count() == 1

            with sessions() as db:
                db.add(RuntimeRecord(id="edit-record", project_id="assign-project", template_id="open-form", status="submitted", submitted_by="assign-admin"))
                db.commit()
            blocked = client.delete(f"/api/v1/builder/components/detail/{second}", headers=admin)
            assert blocked.status_code == 422
            assert "respuestas" in blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_reorder_questions_changes_runtime_order():
    engine, _ = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            ids = _build_form(client, admin, "open-form", ["uno", "dos", "tres"])
            endpoint = "/api/v1/builder/templates/detail/open-form/component-order"

            reordered = client.put(endpoint, headers=admin, json={"component_ids": [ids[2], ids[0], ids[1]]})
            assert reordered.status_code == 200, reordered.text
            assert _runtime_names(client, admin, "open-form") == ["tres", "uno", "dos"]

            assert client.put(endpoint, headers=admin, json={"component_ids": [ids[0], "ajena"]}).status_code == 422
            assert client.put(endpoint, headers=admin, json={"component_ids": [ids[0], ids[0]]}).status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
