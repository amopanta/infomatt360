import json
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.bulk_import import BulkImportJob
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord
from app.services.metrics_service import metrics_service
from app.services.runtime_record_service import runtime_record_service


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="bulk-project", name="Bulk")
        template = BuilderTemplate(id="bulk-template", project_id=project.id, name="Formulario bulk", status="published")
        role = Role(id="bulk-admin-role", name="Admin", permissions="integrations.api_keys.manage")
        basic_role = Role(id="bulk-basic-role", name="Basic", permissions="records.read")
        admin = User(id="bulk-admin", full_name="Admin", document_id="bulk-admin-doc", email="bulk-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="bulk-basic", full_name="Basic", document_id="bulk-basic-doc", email="bulk-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            template,
            role,
            basic_role,
            admin,
            basic,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient) -> dict[str, str]:
    return auth_as(client, "bulk-admin@example.com", "Admin12345!")


def auth_as(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_api_key(client: TestClient, headers: dict[str, str], permissions: list[str]) -> str:
    response = client.post(
        "/api/v1/api-keys/",
        headers=headers,
        json={
            "project_id": "bulk-project",
            "name": "Bulk key",
            "permissions": permissions,
            "rate_limit_profile": "trusted_sync",
        },
    )
    assert response.status_code == 200
    return response.json()["api_key"]


def test_runtime_bulk_save_uses_api_key_and_creates_records():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-run-001",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "device_id": "sync-1",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Ana")}],
                        },
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "device_id": "sync-1",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Beatriz")}],
                        },
                    ],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["received"] == 2
            assert data["job_id"]
            assert data["idempotency_key"] == "bulk-run-001"
            assert data["replayed"] is False
            assert data["created"] == 2
            assert data["failed"] == 0
            assert all(item["status"] == "created" for item in data["results"])

            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 2

            replay = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-run-001",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "device_id": "sync-1",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Ana")}],
                        },
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "device_id": "sync-1",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Beatriz")}],
                        },
                    ],
                },
            )
            assert replay.status_code == 200
            assert replay.json()["replayed"] is True
            assert replay.json()["job_id"] == data["job_id"]
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 2

            job_detail = client.get(f"/api/v1/runtime/bulk/jobs/{data['job_id']}", headers={"X-API-Key": api_key})
            assert job_detail.status_code == 200
            job_data = job_detail.json()
            assert job_data["id"] == data["job_id"]
            assert job_data["idempotency_key"] == "bulk-run-001"
            assert job_data["received"] == 2
            assert job_data["created"] == 2
            assert job_data["failed"] == 0
            assert job_data["response"]["job_id"] == data["job_id"]

            jobs = client.get("/api/v1/runtime/bulk/jobs?template_id=bulk-template", headers={"X-API-Key": api_key})
            assert jobs.status_code == 200
            assert jobs.json()[0]["id"] == data["job_id"]

            conflict = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-run-001",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Cambio")}],
                        },
                    ],
                },
            )
            assert conflict.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_save_rejects_api_key_without_write_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.read"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "records": [
                        {"project_id": "bulk-project", "template_id": "bulk-template", "values": []},
                    ],
                },
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_queued_job_can_be_processed_later():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            payload = {
                "project_id": "bulk-project",
                "template_id": "bulk-template",
                "idempotency_key": "bulk-queued-001",
                "processing_mode": "queued",
                "records": [
                    {
                        "project_id": "bulk-project",
                        "template_id": "bulk-template",
                        "device_id": "sync-queued",
                        "values": [{"field_name": "nombre", "field_value_json": json.dumps("Carolina")}],
                    }
                ],
            }
            response = client.post("/api/v1/runtime/bulk/save", headers={"X-API-Key": api_key}, json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["job_id"]
            assert data["job_status"] == "queued"
            assert data["processing_mode"] == "queued"
            assert data["created"] == 0
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 0

            replay = client.post("/api/v1/runtime/bulk/save", headers={"X-API-Key": api_key}, json=payload)
            assert replay.status_code == 200
            assert replay.json()["replayed"] is True
            assert replay.json()["job_id"] == data["job_id"]
            assert replay.json()["job_status"] == "queued"

            detail = client.get(f"/api/v1/runtime/bulk/jobs/{data['job_id']}", headers={"X-API-Key": api_key})
            assert detail.status_code == 200
            assert detail.json()["status"] == "queued"

            processed = client.post(f"/api/v1/runtime/bulk/jobs/{data['job_id']}/process", headers={"X-API-Key": api_key})
            assert processed.status_code == 200
            processed_data = processed.json()
            assert processed_data["status"] == "completed"
            assert processed_data["created"] == 1
            assert processed_data["failed"] == 0
            assert processed_data["response"]["job_status"] == "completed"
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 1

            processed_again = client.post(f"/api/v1/runtime/bulk/jobs/{data['job_id']}/process", headers={"X-API-Key": api_key})
            assert processed_again.status_code == 200
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_worker_processes_queued_jobs_in_order():
    engine, sessions = setup_client()
    metrics_service.reset()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            for index, name in enumerate(["Uno", "Dos"], start=1):
                response = client.post(
                    "/api/v1/runtime/bulk/save",
                    headers={"X-API-Key": api_key},
                    json={
                        "project_id": "bulk-project",
                        "template_id": "bulk-template",
                        "idempotency_key": f"bulk-worker-{index:03d}",
                        "processing_mode": "queued",
                        "records": [
                            {
                                "project_id": "bulk-project",
                                "template_id": "bulk-template",
                                "values": [{"field_name": "nombre", "field_value_json": json.dumps(name)}],
                            }
                        ],
                    },
                )
                assert response.status_code == 200

            with sessions() as db:
                result = runtime_record_service.process_queued_bulk_jobs(db, limit=1, user_id="worker-test")
                assert result["picked"] == 1
                assert result["processed"] == 1
                assert result["processed_jobs"][0]["status"] == "completed"
                first_job = db.query(BulkImportJob).filter(BulkImportJob.id == result["processed_jobs"][0]["job_id"]).one()
                assert first_job.worker_id == "bulk-worker"
                assert first_job.locked_at is not None
                assert first_job.attempt_count == 1
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 1

                second = runtime_record_service.process_queued_bulk_jobs(db, limit=10, user_id="worker-test")
                assert second["picked"] == 1
                assert second["processed"] == 1
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 2

                empty = runtime_record_service.process_queued_bulk_jobs(db, limit=10, user_id="worker-test")
                assert empty["picked"] == 0
                assert empty["processed"] == 0
                bulk_metrics = metrics_service.bulk_snapshot()
                assert bulk_metrics["worker_cycles"] == 3
                assert bulk_metrics["picked"] == 2
                assert bulk_metrics["processed"] == 2
                assert bulk_metrics["completed_jobs"] == 2
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_worker_marks_job_failed_after_max_attempts():
    engine, sessions = setup_client()
    metrics_service.reset()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-worker-failure-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Falla")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            job_id = response.json()["job_id"]

            with sessions() as db:
                job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                job.payload_json = "{payload-corrupto"
                job.max_attempts = 1
                db.commit()

                result = runtime_record_service.process_queued_bulk_jobs(db, limit=5, user_id="worker-test", worker_id="worker-failure")
                assert result["picked"] == 1
                assert result["processed"] == 0
                assert result["failed"] == 1
                failed_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert failed_job.status == "failed"
                assert failed_job.worker_id is None
                assert failed_job.locked_at is None
                assert failed_job.attempt_count == 1
                assert failed_job.last_error
                assert failed_job.completed_at is not None
                bulk_metrics = metrics_service.bulk_snapshot()
                assert bulk_metrics["worker_cycles"] == 1
                assert bulk_metrics["failed"] == 1
                assert bulk_metrics["failed_jobs"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_worker_waits_for_next_attempt_backoff():
    engine, sessions = setup_client()
    metrics_service.reset()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-worker-backoff-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Reintento")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            job_id = response.json()["job_id"]

            with sessions() as db:
                job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                job.payload_json = "{payload-corrupto"
                job.max_attempts = 2
                db.commit()

                first = runtime_record_service.process_queued_bulk_jobs(db, limit=5, user_id="worker-test", worker_id="worker-backoff")
                assert first["picked"] == 1
                assert first["failed"] == 1
                waiting_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert waiting_job.status == "queued"
                assert waiting_job.attempt_count == 1
                assert waiting_job.next_attempt_at is not None
                assert waiting_job.next_attempt_at > utc_now()

                skipped = runtime_record_service.process_queued_bulk_jobs(db, limit=5, user_id="worker-test", worker_id="worker-backoff")
                assert skipped["picked"] == 0
                assert skipped["processed"] == 0

                waiting_job.next_attempt_at = utc_now() - timedelta(seconds=1)
                db.commit()
                second = runtime_record_service.process_queued_bulk_jobs(db, limit=5, user_id="worker-test", worker_id="worker-backoff")
                assert second["picked"] == 1
                assert second["failed"] == 1
                failed_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert failed_job.status == "failed"
                assert failed_job.attempt_count == 2
                assert failed_job.next_attempt_at is None
                bulk_metrics = metrics_service.bulk_snapshot()
                assert bulk_metrics["retries_scheduled"] == 1
                assert bulk_metrics["failed_jobs"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_worker_recovers_stale_processing_job():
    engine, sessions = setup_client()
    metrics_service.reset()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-worker-stale-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Atascado")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            job_id = response.json()["job_id"]

            with sessions() as db:
                job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                job.status = "processing"
                job.worker_id = "dead-worker"
                job.locked_at = utc_now() - timedelta(hours=2)
                job.attempt_count = 1
                job.max_attempts = 3
                db.commit()

                recovered = runtime_record_service.recover_stale_bulk_jobs(db)
                assert recovered["recovered"] == 1
                assert recovered["failed"] == 0
                recovered_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert recovered_job.status == "queued"
                assert recovered_job.worker_id is None
                assert recovered_job.locked_at is None
                assert recovered_job.next_attempt_at is not None
                assert "timeout" in recovered_job.last_error
                bulk_metrics = metrics_service.bulk_snapshot()
                assert bulk_metrics["retries_scheduled"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_processing_job_refreshes_heartbeat():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-worker-heartbeat-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Heartbeat")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            job_id = response.json()["job_id"]

            old_lock = utc_now() - timedelta(hours=2)
            with sessions() as db:
                job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                job.status = "processing"
                job.worker_id = "heartbeat-worker"
                job.locked_at = old_lock
                job.attempt_count = 1
                db.commit()

                detail = runtime_record_service.process_bulk_job(db, "bulk-project", job_id, "worker-test", worker_id="heartbeat-worker")
                refreshed_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert detail is not None
                assert detail.status == "completed"
                assert refreshed_job.locked_at is not None
                assert refreshed_job.locked_at > old_lock
                assert refreshed_job.worker_id == "heartbeat-worker"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_worker_fails_stale_job_when_attempts_are_exhausted():
    engine, sessions = setup_client()
    metrics_service.reset()
    try:
        with TestClient(app) as client:
            headers = auth(client)
            api_key = create_api_key(client, headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-worker-stale-failed-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Atascado fallido")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            job_id = response.json()["job_id"]

            with sessions() as db:
                job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                job.status = "processing"
                job.worker_id = "dead-worker"
                job.locked_at = utc_now() - timedelta(hours=2)
                job.attempt_count = 3
                job.max_attempts = 3
                db.commit()

                recovered = runtime_record_service.recover_stale_bulk_jobs(db)
                assert recovered["recovered"] == 0
                assert recovered["failed"] == 1
                failed_job = db.query(BulkImportJob).filter(BulkImportJob.id == job_id).one()
                assert failed_job.status == "failed"
                assert failed_job.worker_id is None
                assert failed_job.locked_at is None
                assert failed_job.next_attempt_at is None
                assert failed_job.completed_at is not None
                bulk_metrics = metrics_service.bulk_snapshot()
                assert bulk_metrics["failed_jobs"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_jobs_can_be_managed_from_admin_session():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client)
            basic_headers = auth_as(client, "bulk-basic@example.com", "Basic12345!")
            api_key = create_api_key(client, admin_headers, ["records.write"])
            queued = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-admin-queued-001",
                    "processing_mode": "queued",
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "bulk-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Daniel")}],
                        }
                    ],
                },
            )
            assert queued.status_code == 200
            job_id = queued.json()["job_id"]

            denied = client.get("/api/v1/runtime/bulk/admin/bulk-project/jobs", headers=basic_headers)
            assert denied.status_code == 403

            listed = client.get("/api/v1/runtime/bulk/admin/bulk-project/jobs", headers=admin_headers)
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == job_id
            assert listed.json()[0]["status"] == "queued"

            listed_filtered = client.get("/api/v1/runtime/bulk/admin/bulk-project/jobs?status=queued&template_id=bulk-template", headers=admin_headers)
            assert listed_filtered.status_code == 200
            assert listed_filtered.json()[0]["id"] == job_id

            listed_empty = client.get("/api/v1/runtime/bulk/admin/bulk-project/jobs?status=completed", headers=admin_headers)
            assert listed_empty.status_code == 200
            assert listed_empty.json() == []

            summary = client.get("/api/v1/runtime/bulk/admin/bulk-project/summary", headers=admin_headers)
            assert summary.status_code == 200
            summary_data = summary.json()
            assert summary_data["total_jobs"] == 1
            assert summary_data["queued_jobs"] == 1
            assert summary_data["completed_jobs"] == 0
            assert summary_data["total_received"] == 1

            detail = client.get(f"/api/v1/runtime/bulk/admin/bulk-project/jobs/{job_id}", headers=admin_headers)
            assert detail.status_code == 200
            assert detail.json()["response"]["job_status"] == "queued"

            processed = client.post(f"/api/v1/runtime/bulk/admin/bulk-project/jobs/{job_id}/process", headers=admin_headers)
            assert processed.status_code == 200
            assert processed.json()["status"] == "completed"
            assert processed.json()["created"] == 1
            summary_after = client.get("/api/v1/runtime/bulk/admin/bulk-project/summary", headers=admin_headers)
            assert summary_after.status_code == 200
            assert summary_after.json()["completed_jobs"] == 1
            assert summary_after.json()["success_rate"] == 100
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "bulk-template").count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_runtime_bulk_admin_can_export_failed_items_csv():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client)
            api_key = create_api_key(client, admin_headers, ["records.write"])
            response = client.post(
                "/api/v1/runtime/bulk/save",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": "bulk-project",
                    "template_id": "bulk-template",
                    "idempotency_key": "bulk-errors-001",
                    "continue_on_error": True,
                    "records": [
                        {
                            "project_id": "bulk-project",
                            "template_id": "wrong-template",
                            "values": [{"field_name": "nombre", "field_value_json": json.dumps("Error")}],
                        }
                    ],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["failed"] == 1

            export = client.get(f"/api/v1/runtime/bulk/admin/bulk-project/jobs/{data['job_id']}/errors.csv", headers=admin_headers)
            assert export.status_code == 200
            assert "text/csv" in export.headers["content-type"]
            assert "bulk-errors-001" in export.text
            assert "El registro no coincide" in export.text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
