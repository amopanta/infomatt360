"""Pruebas de Base Espejo real (replicacion a base de datos externa), ver
docs/102 -- cierra el hallazgo #1 de la auditoria de trazabilidad (docs/96).
"""

import os
import sqlite3
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        manager = User(id="mirrortest-manager", full_name="Gestor de Espejo", document_id="mirrortest-manager-doc", email="mirrortest-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="mirrortest-outsider", full_name="Sin permiso", document_id="mirrortest-outsider-doc", email="mirrortest-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="mirrortest-project", name="Proyecto Espejo")
        manager_role = Role(id="mirrortest-manager-role", name="Gestor de espejo", permissions="mirror.manage")
        outsider_role = Role(id="mirrortest-outsider-role", name="Sin espejo", permissions="records.read")
        template = BuilderTemplate(id="mirrortest-template", project_id=project.id, name="Plantilla", status="published")

        from app.models.assignment import UserProjectAssignment

        db.add_all([
            manager, outsider, project, manager_role, outsider_role, template,
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
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


def _seed_record(sessions, record_id: str, project_id: str = "mirrortest-project") -> None:
    with sessions() as db:
        db.add(RuntimeRecord(id=record_id, project_id=project_id, template_id="mirrortest-template", status="submitted", submitted_by="mirrortest-manager"))
        db.add(RuntimeRecordValue(id=f"{record_id}-nombre", record_id=record_id, field_name="nombre", field_value_json='"Prueba"'))
        db.commit()


def test_connecting_target_requires_mirror_manage():
    engine, sessions = setup_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                outsider_headers = auth(client, "mirrortest-outsider@example.com", "Outsider12345!")
                denied = client.post(
                    "/api/v1/mirror/targets", headers=outsider_headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                )
                assert denied.status_code == 403

                manager_headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                allowed = client.post(
                    "/api/v1/mirror/targets", headers=manager_headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                )
                assert allowed.status_code == 200, allowed.text
                assert "conn_json" not in allowed.json()
                assert set(allowed.json().keys()) == {"id", "project_id", "name", "engine", "status"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_test_connection_succeeds_against_real_sqlite_file():
    engine, sessions = setup_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                created = client.post(
                    "/api/v1/mirror/targets", headers=headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                )
                target_id = created.json()["id"]

                tested = client.post(f"/api/v1/mirror/targets/{target_id}/test-connection", headers=headers)
                assert tested.status_code == 200, tested.text
                assert tested.json()["success"] is True

                targets = client.get("/api/v1/mirror/targets/mirrortest-project", headers=headers)
                assert targets.json()[0]["status"] == "active"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_test_connection_fails_against_unreachable_postgres_host():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
            created = client.post(
                "/api/v1/mirror/targets", headers=headers,
                json={
                    "project_id": "mirrortest-project", "name": "Espejo inalcanzable", "engine": "postgres",
                    "host": "host-inexistente-infomatt360-verif.invalid", "port": 5432, "database": "x", "username": "x", "password": "x",
                },
            )
            target_id = created.json()["id"]

            tested = client.post(f"/api/v1/mirror/targets/{target_id}/test-connection", headers=headers)
            assert tested.status_code == 502

            targets = client.get("/api/v1/mirror/targets/mirrortest-project", headers=headers)
            failed_target = next(row for row in targets.json() if row["id"] == target_id)
            assert failed_target["status"] == "connection_error"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_full_mirror_run_replicates_records_and_values():
    engine, sessions = setup_client()
    _seed_record(sessions, "mirrortest-record-1")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                target = client.post(
                    "/api/v1/mirror/targets", headers=headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                ).json()
                plan = client.post(
                    "/api/v1/mirror/plans", headers=headers,
                    json={"target_id": target["id"], "name": "Plan completo", "schedule_mode": "full_mirror"},
                ).json()

                run = client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                assert run.status_code == 200, run.text
                body = run.json()
                assert body["status"] == "completed"
                assert body["records_synced"] == 1
                assert body["values_synced"] == 1

            mirror_con = sqlite3.connect(db_path)
            cur = mirror_con.cursor()
            cur.execute("SELECT id, project_id, status FROM im360_runtime_records")
            rows = cur.fetchall()
            assert rows == [("mirrortest-record-1", "mirrortest-project", "submitted")]
            cur.execute("SELECT field_name, field_value_json FROM im360_runtime_record_values")
            assert cur.fetchall() == [("nombre", '"Prueba"')]
            mirror_con.close()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_full_mirror_run_twice_does_not_duplicate_rows():
    engine, sessions = setup_client()
    _seed_record(sessions, "mirrortest-record-2")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                target = client.post(
                    "/api/v1/mirror/targets", headers=headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                ).json()
                plan = client.post(
                    "/api/v1/mirror/plans", headers=headers,
                    json={"target_id": target["id"], "name": "Plan completo", "schedule_mode": "full_mirror"},
                ).json()

                client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                second = client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                assert second.json()["records_synced"] == 1

            mirror_con = sqlite3.connect(db_path)
            cur = mirror_con.cursor()
            cur.execute("SELECT COUNT(*) FROM im360_runtime_records")
            assert cur.fetchone() == (1,)
            mirror_con.close()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_insert_only_mode_never_touches_existing_rows_but_adds_new_ones():
    engine, sessions = setup_client()
    _seed_record(sessions, "mirrortest-record-3")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                target = client.post(
                    "/api/v1/mirror/targets", headers=headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                ).json()
                plan = client.post(
                    "/api/v1/mirror/plans", headers=headers,
                    json={"target_id": target["id"], "name": "Plan insert-only", "schedule_mode": "insert_only"},
                ).json()

                first = client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                assert first.json()["records_synced"] == 1

            # Se modifica el valor original en el ORIGEN (no en el espejo) despues de la primera corrida.
            with sessions() as db:
                value = db.query(RuntimeRecordValue).filter(RuntimeRecordValue.id == "mirrortest-record-3-nombre").first()
                value.field_value_json = '"Prueba modificada"'
                db.commit()
            _seed_record(sessions, "mirrortest-record-4")

            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                second = client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                assert second.status_code == 200, second.text
                assert second.json()["records_synced"] == 1  # solo el registro nuevo

            mirror_con = sqlite3.connect(db_path)
            cur = mirror_con.cursor()
            cur.execute("SELECT COUNT(*) FROM im360_runtime_records")
            assert cur.fetchone() == (2,)
            cur.execute("SELECT field_value_json FROM im360_runtime_record_values WHERE id = 'mirrortest-record-3-nombre'")
            assert cur.fetchone() == ('"Prueba"',)  # el valor viejo del espejo no se toco
            mirror_con.close()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_run_history_is_listed():
    engine, sessions = setup_client()
    _seed_record(sessions, "mirrortest-record-5")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "mirror.db")
            with TestClient(app) as client:
                headers = auth(client, "mirrortest-manager@example.com", "Manager12345!")
                target = client.post(
                    "/api/v1/mirror/targets", headers=headers,
                    json={"project_id": "mirrortest-project", "name": "Espejo prueba", "engine": "sqlite", "file_path": db_path},
                ).json()
                plan = client.post(
                    "/api/v1/mirror/plans", headers=headers,
                    json={"target_id": target["id"], "name": "Plan completo", "schedule_mode": "full_mirror"},
                ).json()

                client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)
                client.post(f"/api/v1/mirror/plans/{plan['id']}/run", headers=headers)

                runs = client.get(f"/api/v1/mirror/plans/{plan['id']}/runs", headers=headers)
                assert runs.status_code == 200
                assert len(runs.json()) == 2
                assert all(run["status"] == "completed" for run in runs.json())
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
