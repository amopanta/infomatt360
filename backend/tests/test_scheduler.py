import shutil
import tempfile
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User
from app.models.scheduler import ScheduledTask, TaskRun
from app.services.scheduler_service import scheduler_service


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="sched-project", name="Sched Project")
        admin_role = Role(id="sched-admin-role", name="Admin Backup", permissions="backups.manage")
        basic_role = Role(id="sched-basic-role", name="Basico", permissions="records.read")
        admin = User(id="sched-admin", full_name="Admin", document_id="sched-admin-doc", email="sched-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="sched-basic", full_name="Basic", document_id="sched-basic-doc", email="sched-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            admin_role,
            basic_role,
            admin,
            basic,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
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


def test_scheduling_a_backup_task_requires_backups_manage_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            basic_headers = auth(client, "sched-basic@example.com", "Basic12345!")
            denied = client.post(
                "/api/v1/scheduler/tasks",
                headers=basic_headers,
                json={"project_id": "sched-project", "name": "Respaldo automatico", "task_type": "backup", "frequency": "daily"},
            )
            assert denied.status_code == 403

            admin_headers = auth(client, "sched-admin@example.com", "Admin12345!")
            created = client.post(
                "/api/v1/scheduler/tasks",
                headers=admin_headers,
                json={"project_id": "sched-project", "name": "Respaldo automatico", "task_type": "backup", "frequency": "daily"},
            )
            assert created.status_code == 200
            body = created.json()
            assert body["frequency"] == "daily"
            # Se programa para correr pronto (proximo ciclo del worker), no dentro de 24h.
            assert body["next_run_at"] is not None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_run_due_tasks_executes_due_backup_and_reschedules():
    engine, sessions = setup_client()
    temp_dir = tempfile.mkdtemp(prefix="infomatt360-scheduler-test-")
    original_backup_directory = settings.backup_directory
    settings.backup_directory = temp_dir
    try:
        with sessions() as db:
            task = ScheduledTask(
                project_id="sched-project", name="Respaldo automatico", task_type="backup",
                frequency="daily", status="active", next_run_at=utc_now() - timedelta(minutes=5),
            )
            db.add(task)
            db.commit()
            task_id = task.id

        with sessions() as db:
            result = scheduler_service.run_due_tasks(db, limit=10)
            assert result == {"processed": 1, "succeeded": 1, "failed": 0}

        with sessions() as db:
            refreshed = db.get(ScheduledTask, task_id)
            assert refreshed.last_run_at is not None
            assert refreshed.next_run_at > utc_now() + timedelta(hours=23)
            assert "Respaldo completado" in refreshed.last_result

            runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
            assert len(runs) == 1
            assert runs[0].status == "success"
    finally:
        settings.backup_directory = original_backup_directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_run_due_tasks_skips_tasks_not_yet_due_and_manual_frequency():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            not_due = ScheduledTask(
                project_id="sched-project", name="Futuro", task_type="backup",
                frequency="daily", status="active", next_run_at=utc_now() + timedelta(hours=5),
            )
            manual = ScheduledTask(
                project_id="sched-project", name="Manual", task_type="backup",
                frequency="manual", status="active", next_run_at=utc_now() - timedelta(hours=5),
            )
            db.add_all([not_due, manual])
            db.commit()

        with sessions() as db:
            result = scheduler_service.run_due_tasks(db, limit=10)
            assert result == {"processed": 0, "succeeded": 0, "failed": 0}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_run_due_tasks_marks_unsupported_task_type_as_failed():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            task = ScheduledTask(
                project_id="sched-project", name="Tipo desconocido", task_type="report_export",
                frequency="hourly", status="active", next_run_at=utc_now() - timedelta(minutes=1),
            )
            db.add(task)
            db.commit()
            task_id = task.id

        with sessions() as db:
            result = scheduler_service.run_due_tasks(db, limit=10)
            assert result == {"processed": 1, "succeeded": 0, "failed": 1}

        with sessions() as db:
            refreshed = db.get(ScheduledTask, task_id)
            assert "no esta soportado" in refreshed.last_result
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
