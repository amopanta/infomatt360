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
from app.models.builder import BuilderTemplate
from app.models.identity import User


@pytest.fixture(scope="module")
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    active_user = User(id="user-test", full_name="Usuario Test", document_id="1000", email="external@example.com")

    with testing_session() as db:
        db.add_all(
            [
                UserProjectAssignment(user_id=active_user.id, project_id="project-test", status="active"),
                UserProjectAssignment(user_id=active_user.id, project_id="project-cache", status="active"),
                UserProjectAssignment(user_id=active_user.id, project_id="project-other", status="active"),
                BuilderTemplate(id="template-1", project_id="project-test", name="Template 1"),
                BuilderTemplate(id="template-2", project_id="project-test", name="Template 2"),
                BuilderTemplate(id="template-cache", project_id="project-cache", name="Template cache"),
                BuilderTemplate(id="template-other", project_id="project-other", name="Template other"),
            ]
        )
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


def test_external_data_source_round_trip(client):
    client, _ = client
    payload = {
        "project_id": "project-test",
        "name": "Municipios",
        "source_type": "csv_url",
        "source_url": "https://example.com/municipios.csv",
        "key_field": "codigo",
    }

    created = client.post("/api/v1/external-data/sources", json=payload)
    listed = client.get("/api/v1/external-data/sources/project-test")

    assert created.status_code == 200
    assert created.json()["name"] == "Municipios"
    assert listed.status_code == 200
    assert [source["id"] for source in listed.json()] == [created.json()["id"]]


def test_bulk_publish_is_exposed_and_queued(client):
    client, _ = client
    response = client.post(
        "/api/v1/external-data/bulk-publish",
        json={
            "project_id": "project-test",
            "action": "publish",
            "target_template_ids": ["template-1", "template-2"],
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["target_template_ids_json"] == '["template-1", "template-2"]'


def test_runtime_cache_returns_latest_snapshot_by_alias(client):
    client, _ = client
    source = client.post(
        "/api/v1/external-data/sources",
        json={
            "project_id": "project-cache",
            "name": "Municipios cache",
            "source_url": "https://example.com/cache.csv",
            "key_field": "codigo",
        },
    ).json()
    binding = client.post(
        "/api/v1/external-data/bindings",
        json={
            "template_id": "template-cache",
            "data_source_id": source["id"],
            "alias": "municipios",
        },
    )
    first = client.post(
        f"/api/v1/external-data/sources/{source['id']}/snapshots",
        json={"version": "v1", "rows": [{"codigo": 1, "nombre": "Anterior"}]},
    )
    latest = client.post(
        f"/api/v1/external-data/sources/{source['id']}/snapshots",
        json={"version": "v2", "rows": [{"codigo": 1, "nombre": "Actual"}]},
    )
    cache = client.get("/api/v1/external-data/runtime-cache/template-cache")

    assert binding.status_code == 200
    assert first.status_code == 201
    assert latest.status_code == 201
    assert latest.json()["row_count"] == 1
    assert cache.status_code == 200
    assert cache.json() == {
        "municipios": {
            "version": "v2",
            "rows": [{"codigo": 1, "nombre": "Actual"}],
        }
    }


def test_snapshot_rejects_unknown_source(client):
    client, _ = client
    response = client.post(
        "/api/v1/external-data/sources/missing/snapshots",
        json={"version": "v1", "rows": []},
    )

    assert response.status_code == 404


def test_external_data_rejects_user_without_project_access(client):
    test_client, active_user = client
    active_user.id = "other-user"
    try:
        listed = test_client.get("/api/v1/external-data/sources/project-test")
        created = test_client.post(
            "/api/v1/external-data/sources",
            json={"project_id": "project-test", "name": "Ajena", "source_url": "https://example.com/ajena.csv"},
        )
        cache = test_client.get("/api/v1/external-data/runtime-cache/template-cache")
        bulk = test_client.post(
            "/api/v1/external-data/bulk-publish",
            json={"project_id": "project-test", "action": "publish", "target_template_ids": ["template-1"]},
        )
    finally:
        active_user.id = "user-test"

    assert listed.status_code == 403
    assert created.status_code == 403
    assert cache.status_code == 403
    assert bulk.status_code == 403


def test_binding_rejects_cross_project_source(client):
    test_client, _ = client
    source = test_client.post(
        "/api/v1/external-data/sources",
        json={"project_id": "project-test", "name": "Fuente proyecto test", "source_url": "https://example.com/test.csv"},
    ).json()

    response = test_client.post(
        "/api/v1/external-data/bindings",
        json={"template_id": "template-other", "data_source_id": source["id"], "alias": "cruzada"},
    )

    assert response.status_code == 422
