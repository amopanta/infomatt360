import csv
import json
from io import StringIO

import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import User
from app.models.runtime_record import RuntimeRecord
from app.schemas.runtime_record import RuntimeRecordCreate, RuntimeValueCreate
from app.services.runtime_record_service import runtime_record_service


@pytest.fixture(scope="module")
def runtime_context():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with testing_session() as db:
        db.add(BuilderTemplate(id="template-runtime", project_id="project-runtime", name="Runtime Test"))
        db.add(UserProjectAssignment(user_id="runtime-user", project_id="project-runtime", status="active"))
        db.commit()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return User(id="runtime-user", full_name="Runtime User", document_id="2000", email="runtime@example.com")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as test_client:
        yield test_client, testing_session, test_engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_runtime_record_round_trip_supports_repeats(runtime_context):
    client, _, _ = runtime_context
    repeat_value = [
        {"id": "productos_1", "index": 0, "values": {"nombre": "A"}},
        {"id": "productos_2", "index": 1, "values": {"nombre": "B"}},
    ]
    created = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "project-runtime",
            "template_id": "template-runtime",
            "values": [
                {"field_name": "cantidad", "field_value_json": "2"},
                {"field_name": "productos", "field_value_json": json.dumps(repeat_value)},
            ],
        },
    )
    record_id = created.json()["id"]
    fetched = client.get(f"/api/v1/runtime/record/{record_id}")
    listed = client.get("/api/v1/runtime/template/template-runtime/records")

    assert created.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["values"] == created.json()["values"]
    assert [record["id"] for record in listed.json()] == [record_id]


@pytest.mark.parametrize(
    "values",
    [
        [{"field_name": "productos", "field_value_json": "{invalido"}],
        [
            {"field_name": "cantidad", "field_value_json": "1"},
            {"field_name": "cantidad", "field_value_json": "2"},
        ],
    ],
)
def test_runtime_record_rejects_invalid_payloads(runtime_context, values):
    client, _, _ = runtime_context
    response = client.post(
        "/api/v1/runtime/save",
        json={"project_id": "project-runtime", "template_id": "template-runtime", "values": values},
    )

    assert response.status_code == 422


def test_runtime_csv_export_is_excel_compatible_and_formula_safe(runtime_context):
    client, _, _ = runtime_context
    client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "project-runtime",
            "template_id": "template-runtime",
            "values": [{"field_name": "=campo", "field_value_json": json.dumps("=2+2")}],
        },
    )
    response = client.get("/api/v1/runtime/template/template-runtime/records/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Runtime_Test.csv" in response.headers["content-disposition"]
    content = response.content.decode("utf-8")
    assert content.startswith("\ufeff")
    rows = list(csv.reader(StringIO(content.lstrip("\ufeff"))))
    malicious_column = rows[0].index("'=campo")
    assert any(row[malicious_column] == "'=2+2" for row in rows[1:])


def test_runtime_records_search_paginates_and_filters(runtime_context):
    client, testing_session, _ = runtime_context
    with testing_session() as db:
        db.add(BuilderTemplate(id="template-runtime-page", project_id="project-runtime", name="Runtime Page"))
        db.commit()

    for payload in [
        {"status": "submitted", "values": [{"field_name": "nombre", "field_value_json": json.dumps("Ana")}]},
        {"status": "submitted", "values": [{"field_name": "nombre", "field_value_json": json.dumps("Beatriz")}]},
        {"status": "draft", "values": [{"field_name": "nombre", "field_value_json": json.dumps("Carlos")}]},
    ]:
        response = client.post(
            "/api/v1/runtime/save",
            json={"project_id": "project-runtime", "template_id": "template-runtime-page", **payload},
        )
        assert response.status_code == 200

    searched = client.get("/api/v1/runtime/template/template-runtime-page/records/search?search=Ana")
    page = client.get("/api/v1/runtime/template/template-runtime-page/records/search?status=submitted&limit=1&offset=1")
    exported = client.get("/api/v1/runtime/template/template-runtime-page/records/export.csv?search=Ana")

    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["values"][0]["field_value_json"] == json.dumps("Ana")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert exported.status_code == 200
    assert "Ana" in exported.content.decode("utf-8")
    assert "Beatriz" not in exported.content.decode("utf-8")


def test_runtime_record_flags_possible_duplicate_on_identical_resubmission(runtime_context):
    client, testing_session, _ = runtime_context
    with testing_session() as db:
        db.add(BuilderTemplate(id="template-duplicate-check", project_id="project-runtime", name="Duplicate Check"))
        db.commit()

    payload = {
        "project_id": "project-runtime",
        "template_id": "template-duplicate-check",
        "values": [{"field_name": "documento", "field_value_json": json.dumps("123456789")}],
    }
    first = client.post("/api/v1/runtime/save", json=payload)
    second = client.post("/api/v1/runtime/save", json=payload)
    different = client.post(
        "/api/v1/runtime/save",
        json={
            "project_id": "project-runtime",
            "template_id": "template-duplicate-check",
            "values": [{"field_name": "documento", "field_value_json": json.dumps("987654321")}],
        },
    )

    assert first.status_code == 200
    assert first.json()["duplicate_flag"] == "none"
    assert second.status_code == 200
    assert second.json()["duplicate_flag"] == "possible"
    assert different.status_code == 200
    assert different.json()["duplicate_flag"] == "none"


def test_runtime_record_rolls_back_header_when_value_insert_fails(runtime_context):
    _, testing_session, test_engine = runtime_context
    db = testing_session()
    before = db.query(RuntimeRecord).count()
    payload = RuntimeRecordCreate(
        project_id="project-runtime",
        template_id="template-failure",
        values=[RuntimeValueCreate(field_name="campo", field_value_json='"valor"')],
    )

    def fail_value_insert(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("INSERT INTO RUNTIME_RECORD_VALUES"):
            raise RuntimeError("fallo simulado")

    event.listen(test_engine, "before_cursor_execute", fail_value_insert)
    try:
        with pytest.raises(RuntimeError, match="fallo simulado"):
            runtime_record_service.save_record(db, payload, "runtime-user")
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_value_insert)

    assert db.query(RuntimeRecord).count() == before
    db.close()
