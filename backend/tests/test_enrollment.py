from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


def issue_qr_token(client: TestClient, admin_headers: dict[str, str], user_id: str = "qr-manager") -> str:
    created = client.post("/api/v1/enrollment/qr", headers=admin_headers, json={"project_id": "qr-project", "user_id": user_id})
    assert created.status_code == 200
    return created.headers["x-enrollment-token"]


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="qr-project", name="QR Project")
        admin_role = Role(id="qr-admin-role", name="Admin QR", permissions="identity.users.manage")
        manager_role = Role(id="qr-manager-role", name="Gestor", permissions="records.write")
        admin = User(id="qr-admin", full_name="Admin", document_id="qr-admin-doc", email="qr-admin@example.com", password_hash=hash_password("Admin12345!"))
        manager = User(id="qr-manager", full_name="Gestor", document_id="qr-manager-doc", email="qr-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="qr-outsider", full_name="Fuera", document_id="qr-outsider-doc", email="qr-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        db.add_all([
            project,
            admin_role,
            manager_role,
            admin,
            manager,
            outsider,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
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


def test_qr_generation_requires_permission_and_project_membership():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "qr-admin@example.com", "Admin12345!")
            manager_headers = auth(client, "qr-manager@example.com", "Manager12345!")

            denied = client.post("/api/v1/enrollment/qr", headers=manager_headers, json={"project_id": "qr-project", "user_id": "qr-manager"})
            assert denied.status_code == 403

            not_member = client.post("/api/v1/enrollment/qr", headers=admin_headers, json={"project_id": "qr-project", "user_id": "qr-outsider"})
            assert not_member.status_code == 404

            created = client.post("/api/v1/enrollment/qr", headers=admin_headers, json={"project_id": "qr-project", "user_id": "qr-manager"})
            assert created.status_code == 200
            assert created.headers["content-type"] == "image/png"
            assert created.content[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_qr_validation_lifecycle():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "qr-admin@example.com", "Admin12345!")
            created = client.post("/api/v1/enrollment/qr", headers=admin_headers, json={"project_id": "qr-project", "user_id": "qr-manager"})
            raw_token = created.headers["x-enrollment-token"]

            invalid = client.post("/api/v1/enrollment/validate", json={"token": "no-existe"})
            assert invalid.status_code == 401

            valid = client.post("/api/v1/enrollment/validate", json={"token": raw_token, "device_fingerprint": "device-abc"})
            assert valid.status_code == 200
            assert valid.json() == {"valid": True, "project_id": "qr-project", "user_id": "qr-manager"}

            reused = client.post("/api/v1/enrollment/validate", json={"token": raw_token})
            assert reused.status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_device_lock_binds_on_first_enrollment_and_blocks_a_different_device():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "qr-admin@example.com", "Admin12345!")

            first_token = issue_qr_token(client, admin_headers)
            first = client.post("/api/v1/enrollment/validate", json={"token": first_token, "device_fingerprint": "device-A"})
            assert first.status_code == 200

            with sessions() as db:
                user = db.query(User).filter(User.id == "qr-manager").one()
                assert user.locked_device_fingerprint == "device-A"
                assert user.device_lock_updated_at is not None

            second_token = issue_qr_token(client, admin_headers)
            blocked = client.post("/api/v1/enrollment/validate", json={"token": second_token, "device_fingerprint": "device-B"})
            assert blocked.status_code == 403

            # El token del segundo intento (rechazado por dispositivo distinto) no se consume.
            with sessions() as db:
                user = db.query(User).filter(User.id == "qr-manager").one()
                assert user.locked_device_fingerprint == "device-A"

            same_device = client.post("/api/v1/enrollment/validate", json={"token": second_token, "device_fingerprint": "device-A"})
            assert same_device.status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_admin_can_reset_device_lock_to_allow_a_new_device():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "qr-admin@example.com", "Admin12345!")
            manager_headers = auth(client, "qr-manager@example.com", "Manager12345!")

            first_token = issue_qr_token(client, admin_headers)
            client.post("/api/v1/enrollment/validate", json={"token": first_token, "device_fingerprint": "device-A"})

            denied = client.post("/api/v1/enrollment/reset-device", headers=manager_headers, json={"project_id": "qr-project", "user_id": "qr-manager"})
            assert denied.status_code == 403

            reset = client.post("/api/v1/enrollment/reset-device", headers=admin_headers, json={"project_id": "qr-project", "user_id": "qr-manager"})
            assert reset.status_code == 204

            with sessions() as db:
                user = db.query(User).filter(User.id == "qr-manager").one()
                assert user.locked_device_fingerprint is None

            new_token = issue_qr_token(client, admin_headers)
            revalidated = client.post("/api/v1/enrollment/validate", json={"token": new_token, "device_fingerprint": "device-B"})
            assert revalidated.status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
