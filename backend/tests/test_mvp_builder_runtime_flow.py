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
from app.models.identity import Role, User


@pytest.fixture(scope="module")
def mvp_context():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    active_user = User(id="mvp-user", full_name="MVP User", document_id="3000", email="mvp@example.com")

    with testing_session() as db:
        db.add(Role(id="mvp-role", name="Capturista", permissions="records.write,records.read,builder.write"))
        db.add(UserProjectAssignment(user_id=active_user.id, project_id="project-mvp", role_id="mvp-role", status="active"))
        db.commit()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return active_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as test_client:
        yield test_client, active_user
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_builder_runtime_save_query_complete_flow(mvp_context):
    client, _ = mvp_context
    template = client.post(
        "/api/v1/builder/templates",
        json={"project_id": "project-mvp", "name": "Caracterizacion MVP"},
    ).json()
    page = client.post(
        "/api/v1/builder/pages",
        json={"template_id": template["id"], "title": "Datos generales"},
    ).json()
    section = client.post(
        "/api/v1/builder/sections",
        json={"page_id": page["id"], "title": "Identificacion"},
    ).json()
    row = client.post(
        "/api/v1/builder/rows",
        json={"section_id": section["id"]},
    ).json()
    column = client.post(
        "/api/v1/builder/columns",
        json={"row_id": row["id"], "desktop_width": 12, "tablet_width": 12, "mobile_width": 12},
    ).json()
    component = client.post(
        "/api/v1/builder/components",
        json={
            "template_id": template["id"],
            "column_id": column["id"],
            "component_type": "TEXT",
            "name": "nombre",
            "label": "Nombre completo",
        },
    ).json()

    runtime = client.get(f"/api/v1/runtime/template/{template['id']}")
    saved = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "project-mvp",
            "template_id": template["id"],
            "values": [
                {
                    "component_id": component["id"],
                    "field_name": "nombre",
                    "field_value_json": json.dumps("Ana Perez"),
                }
            ],
        },
    )
    records = client.get(f"/api/v1/runtime/template/{template['id']}/records")

    assert runtime.status_code == 200
    runtime_component = runtime.json()["pages"][0]["sections"][0]["rows"][0]["columns"][0]["components"][0]
    assert runtime_component["name"] == "nombre"
    assert saved.status_code == 200
    assert records.status_code == 200
    assert records.json()[0]["id"] == saved.json()["id"]
    assert records.json()[0]["values"][0]["field_value_json"] == '"Ana Perez"'


def test_runtime_rejects_user_without_project_access(mvp_context):
    client, active_user = mvp_context
    templates = client.get("/api/v1/builder/templates/project-mvp").json()
    template_id = templates[0]["id"]
    active_user.id = "other-user"
    try:
        runtime = client.get(f"/api/v1/runtime/template/{template_id}")
        records = client.get(f"/api/v1/runtime/template/{template_id}/records")
    finally:
        active_user.id = "mvp-user"

    assert runtime.status_code == 403
    assert records.status_code == 403


def test_builder_rejects_user_without_project_access(mvp_context):
    client, active_user = mvp_context
    templates = client.get("/api/v1/builder/templates/project-mvp").json()
    template_id = templates[0]["id"]
    pages = client.get(f"/api/v1/builder/pages/{template_id}").json()
    active_user.id = "other-user"
    try:
        page_list = client.get(f"/api/v1/builder/pages/{template_id}")
        create_page = client.post(
            "/api/v1/builder/pages",
            json={"template_id": template_id, "title": "Pagina ajena"},
        )
        create_section = client.post(
            "/api/v1/builder/sections",
            json={"page_id": pages[0]["id"], "title": "Seccion ajena"},
        )
    finally:
        active_user.id = "mvp-user"

    assert page_list.status_code == 403
    assert create_page.status_code == 403
    assert create_section.status_code == 403


def test_builder_rejects_column_from_another_template(mvp_context):
    client, _ = mvp_context
    first_template = client.get("/api/v1/builder/templates/project-mvp").json()[0]
    first_page = client.get(f"/api/v1/builder/pages/{first_template['id']}").json()[0]
    first_section = client.get(f"/api/v1/builder/sections/{first_page['id']}").json()[0]
    first_row = client.get(f"/api/v1/builder/rows/{first_section['id']}").json()[0]
    first_column = client.get(f"/api/v1/builder/columns/{first_row['id']}").json()[0]
    second_template = client.post(
        "/api/v1/builder/templates",
        json={"project_id": "project-mvp", "name": "Segunda plantilla"},
    ).json()

    response = client.post(
        "/api/v1/builder/components",
        json={
            "template_id": second_template["id"],
            "column_id": first_column["id"],
            "component_type": "TEXT",
            "name": "campo_cruzado",
            "label": "Campo cruzado",
        },
    )

    assert response.status_code == 422
