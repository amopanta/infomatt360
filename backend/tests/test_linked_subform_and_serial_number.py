import json

import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Role, User


@pytest.fixture(scope="module")
def linked_context():
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with testing_session() as db:
        db.add(BuilderTemplate(id="linked-parent-template", project_id="linked-project", name="Hogares"))
        db.add(BuilderTemplate(id="linked-child-template", project_id="linked-project", name="Integrantes"))
        db.add(BuilderTemplate(id="other-project-template", project_id="other-project", name="Otro proyecto"))
        db.add(BuilderComponent(
            template_id="linked-parent-template", component_type="LINKED_SUBFORM",
            name="integrantes", label="Integrantes del hogar",
            config_json=json.dumps({"child_template_id": "linked-child-template"}),
        ))
        db.add(BuilderComponent(
            template_id="linked-parent-template", component_type="SERIAL_NUMBER",
            name="consecutivo", label="Consecutivo",
        ))
        db.add(Role(id="linked-role", name="Capturista", permissions="records.write,records.read"))
        db.add(UserProjectAssignment(user_id="linked-user", project_id="linked-project", role_id="linked-role", status="active"))
        db.add(UserProjectAssignment(user_id="linked-user", project_id="other-project", role_id="linked-role", status="active"))
        db.commit()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return User(id="linked-user", full_name="Linked User", document_id="3000", email="linked@example.com")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def _save_parent(client: TestClient) -> str:
    response = client.post(
        "/api/v1/runtime/save",
        json={"project_id": "linked-project", "template_id": "linked-parent-template", "values": [{"field_name": "nombre_hogar", "field_value_json": '"Casa 1"'}]},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_serial_number_is_assigned_automatically_and_increments(linked_context):
    client = linked_context
    first = _save_parent(client)
    second = _save_parent(client)

    first_value = next(v["field_value_json"] for v in client.get(f"/api/v1/runtime/record/{first}").json()["values"] if v["field_name"] == "consecutivo")
    second_value = next(v["field_value_json"] for v in client.get(f"/api/v1/runtime/record/{second}").json()["values"] if v["field_name"] == "consecutivo")

    assert json.loads(first_value) == 1
    assert json.loads(second_value) == 2


def test_serial_number_is_not_overwritten_if_already_provided(linked_context):
    client = linked_context
    response = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "linked-project",
            "template_id": "linked-parent-template",
            "values": [
                {"field_name": "nombre_hogar", "field_value_json": '"Casa preasignada"'},
                {"field_name": "consecutivo", "field_value_json": "999"},
            ],
        },
    )
    assert response.status_code == 200
    value = next(v["field_value_json"] for v in response.json()["values"] if v["field_name"] == "consecutivo")
    assert json.loads(value) == 999


def test_linked_subform_child_is_a_real_separate_record_not_embedded(linked_context):
    client = linked_context
    parent_id = _save_parent(client)

    child_response = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "linked-project",
            "template_id": "linked-child-template",
            "parent_record_id": parent_id,
            "parent_field_name": "integrantes",
            "values": [{"field_name": "nombre_integrante", "field_value_json": '"Ana"'}],
        },
    )
    assert child_response.status_code == 200, child_response.text
    child_body = child_response.json()
    assert child_body["template_id"] == "linked-child-template"
    assert child_body["parent_record_id"] == parent_id
    assert child_body["parent_field_name"] == "integrantes"
    assert child_body["id"] != parent_id  # fila propia, no un valor embebido del padre

    listed = client.get(f"/api/v1/runtime/record/{parent_id}/children/integrantes")
    assert listed.status_code == 200
    children = listed.json()
    assert len(children) == 1
    assert children[0]["id"] == child_body["id"]

    parent_record = client.get(f"/api/v1/runtime/record/{parent_id}").json()
    parent_field_names = {v["field_name"] for v in parent_record["values"]}
    assert "integrantes" not in parent_field_names  # no quedo embebido en el JSON del padre


def test_linked_subform_rejects_parent_from_another_project(linked_context):
    client = linked_context
    parent_id = _save_parent(client)

    response = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "other-project",
            "template_id": "other-project-template",
            "parent_record_id": parent_id,
            "parent_field_name": "integrantes",
            "values": [],
        },
    )
    assert response.status_code == 403
    assert "otro proyecto" in response.text.lower()


def test_linked_subform_rejects_nonexistent_parent(linked_context):
    client = linked_context
    response = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "linked-project",
            "template_id": "linked-child-template",
            "parent_record_id": "does-not-exist",
            "parent_field_name": "integrantes",
            "values": [],
        },
    )
    assert response.status_code == 404
    assert "no existe" in response.text.lower()
