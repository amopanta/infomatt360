from datetime import timedelta

from jose import jwt
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
from app.models.emergency_access import EmergencyAccessKey
from app.models.identity import Project, Role, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="emg-project", name="Emergency Project")
        issuer_role = Role(id="emg-issuer-role", name="Issuer", permissions="identity.users.manage")
        outsider_role = Role(id="emg-outsider-role", name="Sin permiso", permissions="records.read")

        issuer = User(id="emg-issuer", full_name="Issuer", document_id="emg-issuer-doc", email="emg-issuer@example.com", password_hash=hash_password("Issuer12345!"))
        outsider = User(id="emg-outsider", full_name="Outsider", document_id="emg-outsider-doc", email="emg-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        target = User(id="emg-target", full_name="Gestor bloqueado", document_id="emg-target-doc", email="emg-target@example.com", password_hash=hash_password("Target12345!"))
        unaffiliated_target = User(
            id="emg-unaffiliated-target",
            full_name="Sin acceso al proyecto",
            document_id="emg-unaffiliated-target-doc",
            email="emg-unaffiliated-target@example.com",
            password_hash=hash_password("Unaffiliated12345!"),
        )

        db.add_all([
            project,
            issuer_role,
            outsider_role,
            issuer,
            outsider,
            target,
            unaffiliated_target,
            UserProjectAssignment(user_id=issuer.id, project_id=project.id, role_id=issuer_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
            UserProjectAssignment(user_id=target.id, project_id=project.id, role_id=outsider_role.id, status="active"),
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


def test_issue_requires_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-outsider@example.com", "Outsider12345!")
            response = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 24},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_issue_rejects_target_user_without_project_access():
    """Regresion IDOR: el emisor no deberia poder acuñar una credencial de
    emergencia para un usuario que no tiene ninguna asignacion al proyecto
    indicado, aunque el usuario exista en el sistema."""
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            response = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-unaffiliated-target", "hours_valid": 24},
            )
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_redeem_caps_session_length_to_normal_jwt_expiry():
    """La sesion emitida al canjear nunca debe durar mas que la expiracion
    normal de un JWT, aunque la llave de emergencia tenga mucho mas tiempo
    restante (ej. hours_valid=168)."""
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            issued = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 168},
            ).json()

            redeemed = client.post("/api/v1/emergency-access/redeem", json={"code": issued["code"]})
            assert redeemed.status_code == 200
            token = redeemed.json()["access_token"]

            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            issued_at = utc_now()
            token_lifetime = payload["exp"] - int(issued_at.timestamp())
            assert token_lifetime <= settings.access_token_expire_minutes * 60 + 5
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_issue_returns_code_once_and_hides_it_afterwards():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            issued = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 24, "purpose": "auditor externo"},
            )
            assert issued.status_code == 200
            body = issued.json()
            assert "code" in body
            assert len(body["code"]) == 8

            listed = client.get("/api/v1/emergency-access/keys/project/emg-project", headers=headers)
            assert listed.status_code == 200
            assert "code" not in listed.json()[0]
            assert "code_hash" not in listed.json()[0]

            with sessions() as db:
                row = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.id == body["id"]).one()
                assert row.code_hash != body["code"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_redeem_grants_session_for_target_user_and_is_single_use():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            issued = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 1},
            ).json()

            redeemed = client.post("/api/v1/emergency-access/redeem", json={"code": issued["code"]})
            assert redeemed.status_code == 200
            token = redeemed.json()["access_token"]

            session = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
            assert session.status_code == 200
            assert session.json()["user_id"] == "emg-target"

            replay = client.post("/api/v1/emergency-access/redeem", json={"code": issued["code"]})
            assert replay.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_redeem_rejects_expired_key():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            issued = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 1},
            ).json()

            with sessions() as db:
                row = db.query(EmergencyAccessKey).filter(EmergencyAccessKey.id == issued["id"]).one()
                row.expires_at = utc_now() - timedelta(hours=1)
                db.commit()

            redeemed = client.post("/api/v1/emergency-access/redeem", json={"code": issued["code"]})
            assert redeemed.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_revoke_prevents_redemption():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "emg-issuer@example.com", "Issuer12345!")
            issued = client.post(
                "/api/v1/emergency-access/keys",
                headers=headers,
                json={"project_id": "emg-project", "user_id": "emg-target", "hours_valid": 24},
            ).json()

            revoked = client.post(f"/api/v1/emergency-access/keys/{issued['id']}/revoke", headers=headers)
            assert revoked.status_code == 200
            assert revoked.json()["revoked_at"] is not None

            redeemed = client.post("/api/v1/emergency-access/redeem", json={"code": issued["code"]})
            assert redeemed.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_redeem_rejects_unknown_code():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/emergency-access/redeem", json={"code": "DEADBEEF"})
            assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
