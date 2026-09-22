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
        municipality_component = BuilderComponent(template_id=template.id, component_type="TEXT", name="municipio", label="Municipio", sort_order=3)
        sector_component = BuilderComponent(template_id=template.id, component_type="SELECT", name="sector", label="Sector", sort_order=4)

        db.add_all([
            project, other_project,
            builder_role, basic_role,
            builder, basic,
            template, other_template, component, text_component, municipality_component, sector_component,
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
                RuntimeRecordValue(record_id=record_id, field_name="municipio", field_value_json=json.dumps("Bogotá" if record_id != "board-record-3" else "Soacha")),
                RuntimeRecordValue(record_id=record_id, field_name="sector", field_value_json=json.dumps("Educación" if record_id != "board-record-3" else "Salud")),
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


def test_named_indicator_report_goals_municipalities_and_revocable_public_link():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder = auth(client, "board-builder@example.com", "Builder12345!")
            basic = auth(client, "board-basic@example.com", "Basic12345!")
            payload = {
                "project_id": "board-project", "name": "Avance territorial", "description": "Meta de hogares",
                "indicators": [
                    {"title": "Hogares", "template_id": "board-template", "aggregation": "count", "goal": 4, "municipality_field": "municipio", "view_kind": "bar"},
                    {"title": "Integrantes", "template_id": "board-template", "value_field": "integrantes", "aggregation": "sum", "goal": 15, "municipality_field": "municipio"},
                    {"title": "Municipios cubiertos", "template_id": "board-template", "value_field": "municipio", "aggregation": "unique_count", "goal": 3},
                    {"title": "Presupuesto ejecutado", "source_mode": "manual", "manual_actual": 25, "goal": 100},
                ],
            }
            assert client.post("/api/v1/reports/catalog", headers=basic, json=payload).status_code == 403
            created = client.post("/api/v1/reports/catalog", headers=builder, json=payload)
            assert created.status_code == 200, created.text
            report_id = created.json()["id"]
            assert len(client.get("/api/v1/reports/catalog/project/board-project", headers=basic).json()) == 1
            result = client.get(f"/api/v1/reports/catalog/{report_id}", headers=basic)
            assert result.status_code == 200, result.text
            indicators = result.json()["indicators"]
            assert indicators[0]["actual"] == 3
            assert indicators[0]["progress_percent"] == 75
            assert indicators[0]["view_kind"] == "bar"
            assert {item["municipality"]: item["value"] for item in indicators[0]["municipalities"]} == {"Bogotá": 2, "Soacha": 1}
            assert indicators[1]["actual"] == 12
            assert indicators[2]["actual"] == 2
            assert indicators[3]["actual"] == 25
            assert indicators[3]["progress_percent"] == 25
            assert client.get("/api/v1/reports/catalog/does-not-exist", headers=builder).status_code == 404

            updated = client.put(f"/api/v1/reports/catalog/{report_id}", headers=builder, json={**payload, "name": "Avance territorial actualizado"})
            assert updated.status_code == 200, updated.text
            assert updated.json()["name"] == "Avance territorial actualizado"

            shared = client.post(f"/api/v1/reports/catalog/{report_id}/links", headers=builder, json={})
            assert shared.status_code == 200, shared.text
            token = shared.json()["token"]
            public = client.get(f"/api/v1/reports/shared/{token}")
            assert public.status_code == 200, public.text
            assert public.json()["name"] == "Avance territorial actualizado"
            assert public.json()["indicators"][0]["actual"] == 3
            assert "records" not in public.json()
            link_id = shared.json()["id"]
            assert client.post(f"/api/v1/reports/catalog/{report_id}/links/{link_id}/revoke", headers=builder).status_code == 200
            assert client.get(f"/api/v1/reports/shared/{token}").status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_named_report_rejects_cross_project_and_non_numeric_sources():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder = auth(client, "board-builder@example.com", "Builder12345!")
            base = {"project_id": "board-project", "name": "Meta", "indicators": [{"title": "Dato", "template_id": "board-other-template", "aggregation": "count", "goal": 5}]}
            assert client.post("/api/v1/reports/catalog", headers=builder, json=base).status_code == 422
            base["indicators"][0].update(template_id="board-template", value_field="nombre", aggregation="sum")
            assert client.post("/api/v1/reports/catalog", headers=builder, json=base).status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_committee_report_keeps_manual_sections_and_live_form_indicators():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder = auth(client, "board-builder@example.com", "Builder12345!")
            payload = {
                "project_id": "board-project", "name": "Comité mensual", "report_kind": "committee",
                "indicators": [
                    {"title": "Hogares", "template_id": "board-template", "goal": 4},
                    {"title": "Talleres", "source_mode": "manual", "manual_actual": 2, "goal": 3},
                ],
                "committee": {
                    "location": "Bogotá", "audience": "Comité directivo",
                    "activities": [{"title": "Convocatoria", "progress": 80}],
                    "alerts": [{"title": "Cobertura", "priority": "high", "owner": "Coordinación"}],
                    "budget": [{"component": "Talleres", "planned": 100, "spent": 80}],
                    "previous_agreements": [{"title": "Aprobar plan", "status": "done"}],
                    "new_agreements": [{"title": "Ampliar convocatoria", "owner": "Equipo", "due_date": "2026-10-01"}],
                },
            }
            created = client.post("/api/v1/reports/catalog", headers=builder, json=payload)
            assert created.status_code == 200, created.text
            report_id = created.json()["id"]
            result = client.get(f"/api/v1/reports/catalog/{report_id}", headers=builder)
            assert result.status_code == 200, result.text
            assert result.json()["report_kind"] == "committee"
            assert result.json()["indicators"][0]["actual"] == 3
            assert result.json()["indicators"][1]["actual"] == 2
            assert result.json()["committee"]["budget"][0]["spent"] == 80
            assert result.json()["committee"]["new_agreements"][0]["owner"] == "Equipo"
            link = client.post(f"/api/v1/reports/catalog/{report_id}/links", headers=builder, json={}).json()
            shared = client.get(f"/api/v1/reports/shared/{link['token']}")
            assert shared.status_code == 200
            assert shared.json()["committee"]["alerts"][0]["title"] == "Cobertura"
            assert shared.json()["indicators"][0]["actual"] == 3
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_individual_form_report_summarizes_questions_without_raw_text():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            basic = auth(client, "board-basic@example.com", "Basic12345!")
            response = client.get("/api/v1/reports/forms/board-template", headers=basic)
            assert response.status_code == 200, response.text
            report = response.json()
            assert report["records_total"] == 3
            assert report["records_by_status"] == {"submitted": 2, "approved": 1}
            questions = {item["name"]: item for item in report["questions"]}
            assert questions["integrantes"]["numeric_average"] == 4
            assert questions["integrantes"]["answered"] == 3
            assert {item["label"]: item["count"] for item in questions["sector"]["choices"]} == {"Educación": 2, "Salud": 1}
            assert questions["nombre"]["choices"] == []
            assert "Hogar board-record-1" not in response.text
            assert client.get("/api/v1/reports/forms/board-other-template", headers=basic).status_code == 403
            assert client.get("/api/v1/reports/forms/missing", headers=basic).status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
