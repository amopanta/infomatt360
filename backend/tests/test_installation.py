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
