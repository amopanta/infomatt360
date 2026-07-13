from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.middleware.install_guard as install_guard_module
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


BOOTSTRAP_PAYLOAD = {
    "organization_name": "Fundacion Piloto",
    "organization_slug": "fundacion-piloto",
    "project_name": "Proyecto Piloto",
    "admin_full_name": "Admin Instalador",
    "admin_document_id": "install-admin-doc",
    "admin_email": "install-admin@example.com",
    "admin_password": "InstallAdmin12345!",
}


def test_requirements_reports_database_and_uploads_ok():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/install/requirements")
            assert response.status_code == 200
            body = response.json()
            checks_by_key = {check["key"]: check for check in body["checks"]}
            assert checks_by_key["database"]["status"] == "ok"
            assert checks_by_key["uploads"]["status"] == "ok"
            assert body["ready"] is True
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_status_reports_installed_when_installer_disabled():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/install/status")
            assert response.status_code == 200
            assert response.json() == {"installed": True, "installer_enforced": False}
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_bootstrap_rejected_when_installer_disabled():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD)
            assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_bootstrap_creates_admin_stack_and_is_idempotent_when_enforced():
    engine, sessions = setup_client()
    original_enforced = settings.installer_enforced
    original_session_local = install_guard_module.SessionLocal
    settings.installer_enforced = True
    # El middleware abre su propia sesion (no pasa por Depends(get_db)); se
    # apunta a la misma base de prueba aislada para que vea las mismas filas.
    install_guard_module.SessionLocal = sessions
    try:
        with TestClient(app) as client:
            status_before = client.get("/api/v1/install/status")
            assert status_before.json() == {"installed": False, "installer_enforced": True}

            created = client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD)
            assert created.status_code == 200
            body = created.json()
            assert body["organization_id"]
            assert body["project_id"]
            assert body["role_id"]
            assert body["user_id"]

            status_after = client.get("/api/v1/install/status")
            assert status_after.json() == {"installed": True, "installer_enforced": True}

            duplicate = client.post("/api/v1/install/bootstrap", json=BOOTSTRAP_PAYLOAD)
            assert duplicate.status_code == 409

            login = client.post("/api/v1/auth/login", json={"email": "install-admin@example.com", "password": "InstallAdmin12345!"})
            assert login.status_code == 200
    finally:
        settings.installer_enforced = original_enforced
        install_guard_module.SessionLocal = original_session_local
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_bootstrap_creates_optional_mail_storage_and_backup_when_provided():
    engine, sessions = setup_client()
    original_enforced = settings.installer_enforced
    original_session_local = install_guard_module.SessionLocal
    settings.installer_enforced = True
    install_guard_module.SessionLocal = sessions
    try:
        with TestClient(app) as client:
            payload = {
                **BOOTSTRAP_PAYLOAD,
                "organization_slug": "fundacion-piloto-completa",
                "admin_email": "install-admin-completo@example.com",
                "organization_public_url": "https://fundacion-piloto.org",
                "mail": {"sender_email": "notificaciones@fundacion-piloto.org", "server_host": "smtp.fundacion-piloto.org", "server_port": "587"},
                "storage": {"max_file_size_mb": 40},
                "backup": {"frequency": "daily"},
            }
            created = client.post("/api/v1/install/bootstrap", json=payload)
            assert created.status_code == 200, created.text
            body = created.json()
            assert body["mail_profile_id"]
            assert body["storage_profile_id"]
            assert body["scheduled_task_id"]

            with sessions() as db:
                from app.models.messages import MailProfile
                from app.models.organization import Organization
                from app.models.scheduler import ScheduledTask
                from app.models.storage import StorageProfile

                organization = db.query(Organization).filter(Organization.id == body["organization_id"]).one()
                assert organization.public_url == "https://fundacion-piloto.org"

                mail_profile = db.query(MailProfile).filter(MailProfile.id == body["mail_profile_id"]).one()
                assert mail_profile.sender_email == "notificaciones@fundacion-piloto.org"
                assert mail_profile.project_id == body["project_id"]

                storage_profile = db.query(StorageProfile).filter(StorageProfile.id == body["storage_profile_id"]).one()
                assert storage_profile.provider == "local"
                assert storage_profile.max_file_size_mb == 40

                scheduled_task = db.query(ScheduledTask).filter(ScheduledTask.id == body["scheduled_task_id"]).one()
                assert scheduled_task.task_type == "backup"
                assert scheduled_task.frequency == "daily"
                assert scheduled_task.target_id == body["storage_profile_id"]
                assert scheduled_task.next_run_at is not None
    finally:
        settings.installer_enforced = original_enforced
        install_guard_module.SessionLocal = original_session_local
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
