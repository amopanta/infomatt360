import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


@pytest.fixture(scope="module")
def client():
    """Ejecuta Identity sobre una base efimera y aislada del entorno local."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with testing_session() as db:
        project = Project(id="identity-project", name="Proyecto Identity")
        role = Role(
            id="identity-admin-role",
            name="Admin Identity",
            permissions="identity.users.manage,organizations.manage",
        )
        admin = User(
            id="identity-admin",
            full_name="Admin Identity",
            document_id="identity-admin-doc",
            email="identity-admin@example.com",
            password_hash=hash_password("AdminPassword123"),
        )
        db.add_all([
            project,
            role,
            admin,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=role.id, status="active"),
        ])
        db.commit()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "identity-admin@example.com", "password": "AdminPassword123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_user_with_all_channels(client: TestClient) -> None:
    payload = {
        "full_name": "Gestor de Campo",
        "document_id": "123456789",
        "email": "gestor@example.com",
        "allowed_channels": ["web", "android", "desktop"]
    }
    response = client.post("/api/v1/identity/users", json=payload, headers=auth(client))
    assert response.status_code == 201
    data = response.json()
    assert data["document_id"] == payload["document_id"]
    assert "android" in data["allowed_channels"]


def test_create_user_requires_authentication(client: TestClient) -> None:
    payload = {
        "full_name": "Sin sesion",
        "document_id": "000000000",
        "email": "sinsesion@example.com",
        "allowed_channels": ["web"]
    }
    response = client.post("/api/v1/identity/users", json=payload)
    assert response.status_code == 401


def test_list_users_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/identity/users")
    assert response.status_code == 401


def test_create_project(client: TestClient) -> None:
    response = client.post("/api/v1/identity/projects", json={"name": "Proyecto Piloto"}, headers=auth(client))
    assert response.status_code == 201
    assert response.json()["name"] == "Proyecto Piloto"


def test_create_role_with_permissions(client: TestClient) -> None:
    payload = {
        "name": "Coordinador",
        "permissions": ["records.read", "records.approve", "reports.export"]
    }
    response = client.post("/api/v1/identity/roles", json=payload, headers=auth(client))
    assert response.status_code == 201
    data = response.json()
    assert "records.approve" in data["permissions"]


def test_create_role_requires_permission(client: TestClient) -> None:
    payload = {"name": "Sin permiso", "permissions": ["records.read"]}
    response = client.post("/api/v1/identity/roles", json=payload)
    assert response.status_code == 401
