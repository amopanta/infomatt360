import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


@pytest.fixture()
def auth_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="session-user", full_name="Ana Gestora", document_id="session-doc", email="ana@example.com", password_hash=hash_password("Clave123"))
        role = Role(id="coordinator", name="Coordinador", permissions="records.read,reports.export")
        active = Project(id="project-active", name="Proyecto Activo", status="active")
        inactive = Project(id="project-inactive", name="Proyecto Cerrado", status="closed")
        db.add_all([
            user,
            role,
            active,
            inactive,
            UserProjectAssignment(user_id=user.id, project_id=active.id, role_id="coordinator", status="active"),
            UserProjectAssignment(user_id=user.id, project_id=inactive.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_login_and_session_only_return_active_assigned_projects(auth_client):
    login = auth_client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "Clave123"})
    assert login.status_code == 200
    assert login.json()["refresh_token"] is None
    assert "httponly" in login.headers["set-cookie"].lower()
    assert auth_client.cookies.get(settings.refresh_cookie_name)
    token = login.json()["access_token"]
    session = auth_client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 200
    assert session.json() == {
        "user_id": "session-user",
        "full_name": "Ana Gestora",
        "email": "ana@example.com",
        "must_change_password": False,
        "projects": [{"id": "project-active", "name": "Proyecto Activo", "role_id": "coordinator", "permissions": ["records.read", "reports.export"]}],
    }


def test_logout_clears_refresh_cookie(auth_client):
    login = auth_client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "Clave123"})
    token = login.json()["access_token"]
    assert auth_client.cookies.get(settings.refresh_cookie_name)

    logout = auth_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert logout.status_code == 200
    assert settings.refresh_cookie_name not in auth_client.cookies


def test_cookie_refresh_requires_allowed_origin_in_production(auth_client):
    original_environment = settings.environment
    original_frontend_url = settings.frontend_url
    original_cors = settings.cors_allowed_origins
    settings.environment = "production"
    settings.frontend_url = "https://app.infomatt360.test"
    settings.cors_allowed_origins = "https://app.infomatt360.test"
    try:
        login = auth_client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "Clave123"})
        assert login.status_code == 200

        blocked = auth_client.post("/api/v1/auth/refresh", json={})
        assert blocked.status_code == 403

        allowed = auth_client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": "https://app.infomatt360.test"},
            json={},
        )
        assert allowed.status_code == 200
        assert allowed.json()["access_token"]
    finally:
        settings.environment = original_environment
        settings.frontend_url = original_frontend_url
        settings.cors_allowed_origins = original_cors


def test_session_requires_token(auth_client):
    assert auth_client.get("/api/v1/auth/session").status_code == 401
