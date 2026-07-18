import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="board-project", name="Board Project")
        other_project = Project(id="board-other-project", name="Otro proyecto")
        builder_role = Role(id="board-builder-role", name="Builder", permissions="builder.write")
        basic_role = Role(id="board-basic-role", name="Basico", permissions="records.read")
        builder = User(id="board-builder", full_name="Builder", document_id="board-builder-doc", email="board-builder@example.com", password_hash=hash_password("Builder12345!"))
        basic = User(id="board-basic", full_name="Basic", document_id="board-basic-doc", email="board-basic@example.com", password_hash=hash_password("Basic12345!"))

        template = BuilderTemplate(id="board-template", project_id=project.id, name="Caracterizacion", status="published")
        other_template = BuilderTemplate(id="board-other-template", project_id=other_project.id, name="Otro formulario", status="published")
        component = BuilderComponent(template_id=template.id, component_type="NUMBER", name="integrantes", label="Numero de integrantes", sort_order=1)
        text_component = BuilderComponent(template_id=template.id, component_type="TEXT", name="nombre", label="Nombre", sort_order=2)

        db.add_all([
            project, other_project,
            builder_role, basic_role,
            builder, basic,
            template, other_template, component, text_component,
            UserProjectAssignment(user_id=builder.id, project_id=project.id, role_id=builder_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
        ])

        records = [
            ("board-record-1", "submitted", 4),
            ("board-record-2", "submitted", 5),
            ("board-record-3", "approved", 3),
        ]
        for record_id, record_status, integrantes in records:
            db.add(RuntimeRecord(id=record_id, project_id=project.id, template_id=template.id, status=record_status))
            db.add_all([
                RuntimeRecordValue(record_id=record_id, field_name="integrantes", field_value_json=json.dumps(integrantes)),
                RuntimeRecordValue(record_id=record_id, field_name="nombre", field_value_json=json.dumps(f"Hogar {record_id}")),
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


CUSTOM_METRIC_KPI = {
    "type": "kpi",
    "title": "Promedio de integrantes",
    "source": {"kind": "custom_metric", "template_id": "board-template", "field_name": "integrantes", "aggregation": "average"},
}


def test_get_board_without_saved_config_returns_default_widgets_resolved():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            response = client.get("/api/v1/reports/project/board-project/board", headers=headers)
            assert response.status_code == 200, response.text
            body = response.json()
            assert [w["type"] for w in body["widgets"]] == ["kpi", "table", "chart"]
            assert body["resolved"][0] == {"kind": "kpi", "value": 3.0, "display": "3"}
            assert body["resolved"][1] == {"kind": "table"}
            chart_points = {point["label"]: point["value"] for point in body["resolved"][2]["points"]}
            assert chart_points == {"submitted": 2.0, "approved": 1.0}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_update_board_requires_builder_write():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            basic_headers = auth(client, "board-basic@example.com", "Basic12345!")
            response = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=basic_headers,
                json={"project_id": "board-project", "widgets": [CUSTOM_METRIC_KPI]},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_update_board_rejects_non_numeric_field_with_sum_aggregation():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            response = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=headers,
                json={
                    "project_id": "board-project",
                    "widgets": [{
                        "type": "kpi",
                        "title": "Suma de nombres (invalido)",
                        "source": {"kind": "custom_metric", "template_id": "board-template", "field_name": "nombre", "aggregation": "sum"},
                    }],
                },
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_update_board_rejects_template_from_another_project():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            response = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=headers,
                json={
                    "project_id": "board-project",
                    "widgets": [{
                        "type": "kpi",
                        "title": "Cruzado",
                        "source": {"kind": "custom_metric", "template_id": "board-other-template", "field_name": "integrantes", "aggregation": "count"},
                    }],
                },
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_update_then_get_round_trips_custom_metric_average():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            updated = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=headers,
                json={"project_id": "board-project", "widgets": [CUSTOM_METRIC_KPI]},
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["resolved"][0]["value"] == 4.0  # (4 + 5 + 3) / 3

            fetched = client.get("/api/v1/reports/project/board-project/board", headers=headers)
            assert fetched.status_code == 200
            assert fetched.json()["widgets"] == [CUSTOM_METRIC_KPI]
            assert fetched.json()["resolved"][0]["value"] == 4.0
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_custom_metric_by_status_chart_groups_correctly():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            response = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=headers,
                json={
                    "project_id": "board-project",
                    "widgets": [{
                        "type": "chart",
                        "title": "Integrantes por estado",
                        "chart_kind": "bar",
                        "source": {"kind": "custom_metric_by_status", "template_id": "board-template", "field_name": "integrantes", "aggregation": "sum"},
                    }],
                },
            )
            assert response.status_code == 200, response.text
            points = {point["label"]: point["value"] for point in response.json()["resolved"][0]["points"]}
            assert points == {"submitted": 9.0, "approved": 3.0}  # 4+5=9, 3
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_status_breakdown_and_template_totals_match_project_summary():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "board-builder@example.com", "Builder12345!")
            summary = client.get("/api/v1/reports/project/board-project/summary", headers=headers).json()

            board = client.put(
                "/api/v1/reports/project/board-project/board",
                headers=headers,
                json={
                    "project_id": "board-project",
                    "widgets": [
                        {"type": "chart", "title": "Por estado", "chart_kind": "pie", "source": {"kind": "status_breakdown"}},
                        {"type": "chart", "title": "Por formulario", "chart_kind": "bar", "source": {"kind": "template_totals"}},
                    ],
                },
            ).json()

            status_points = {point["label"]: point["value"] for point in board["resolved"][0]["points"]}
            assert status_points == {status_name: float(count) for status_name, count in summary["records_by_status"].items()}

            template_points = {point["label"]: point["value"] for point in board["resolved"][1]["points"]}
            expected_template_points = {item["template_name"]: float(item["records_total"]) for item in summary["templates"]}
            assert template_points == expected_template_points
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
