import time

import pytest
from pydantic import ValidationError
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
from app.models.audit import AuditLog
from app.models.identity import PasswordResetToken, Project, RefreshToken, Role, User
from app.schemas.auth import PasswordResetRequest
from app.services.auth_service import auth_service
from app.services.mfa_service import mfa_service


@pytest.fixture()
def security_context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        admin = User(id="admin", full_name="Administradora", document_id="admin-doc", email="admin@example.com", password_hash=hash_password("AdminPassword123"))
        target = User(id="target", full_name="Persona Campo", document_id="target-doc", email="target@example.com", password_hash=hash_password("TargetPassword123"))
        outsider = User(id="outsider", full_name="Otro Proyecto", document_id="other-doc", email="other@example.com", password_hash=hash_password("OtherPassword123"))
        project = Project(id="project", name="Proyecto", status="active")
        other_project = Project(id="other-project", name="Otro", status="active")
        role = Role(id="admin-role", name="Administrador", permissions="identity.users.manage")
        no_permission = Role(id="basic-role", name="Basico", permissions="records.read")
        db.add_all([
            admin, target, outsider, project, other_project, role, no_permission,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=role.id, status="active"),
            UserProjectAssignment(user_id=target.id, project_id=project.id, role_id=no_permission.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=other_project.id, role_id=no_permission.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_password_policy_rejects_bcrypt_truncation():
    with pytest.raises(ValidationError, match="72 bytes"):
        PasswordResetRequest(
            token="x" * 32,
            new_password="á" * 40,
            confirm_password="á" * 40,
        )


def test_login_is_temporarily_limited_after_repeated_failures(security_context):
    client, _ = security_context
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "target@example.com", "password": "incorrecta"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "target@example.com", "password": "incorrecta"},
    )
    assert blocked.status_code == 429


def test_forgot_password_rate_limit_keeps_neutral_response(security_context):
    client, sessions = security_context
    responses = [
        client.post("/api/v1/auth/password/forgot", json={"email": "target@example.com"})
        for _ in range(5)
    ]
    assert all(response.status_code == 200 for response in responses)
    assert len({response.text for response in responses}) == 1
    with sessions() as db:
        assert db.query(PasswordResetToken).count() == 3


def test_self_change_requires_current_password_and_invalidates_old_token(security_context):
    client, _ = security_context
    token = login(client, "target@example.com", "TargetPassword123")
    denied = client.post("/api/v1/auth/password/change", headers={"Authorization": f"Bearer {token}"}, json={"current_password": "incorrecta", "new_password": "A much safer password 2026", "confirm_password": "A much safer password 2026"})
    assert denied.status_code == 401
    changed = client.post("/api/v1/auth/password/change", headers={"Authorization": f"Bearer {token}"}, json={"current_password": "TargetPassword123", "new_password": "A much safer password 2026", "confirm_password": "A much safer password 2026"})
    assert changed.status_code == 200
    assert client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    login(client, "target@example.com", "A much safer password 2026")


def test_logout_revokes_existing_tokens_and_is_audited(security_context):
    client, sessions = security_context
    token = login(client, "target@example.com", "TargetPassword123")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert client.get("/api/v1/auth/session", headers=headers).status_code == 401
    with sessions() as db:
        log = db.query(AuditLog).filter(
            AuditLog.entity_id == "target",
            AuditLog.action == "logout_all_sessions",
        ).one()
        assert log.user_id == "target"


def test_refresh_rotation_detects_reuse_and_revokes_family(security_context):
    client, sessions = security_context
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "target@example.com", "password": "TargetPassword123"},
    )
    signed_in = login_response.json()
    assert signed_in["refresh_token"] is None
    assert "httponly" in login_response.headers["set-cookie"].lower()
    first_refresh = client.cookies.get(settings.refresh_cookie_name)
    assert first_refresh
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={},
    )
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] is None
    second_refresh = client.cookies.get(settings.refresh_cookie_name)
    assert second_refresh and second_refresh != first_refresh
    assert client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    ).status_code == 200

    reused = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reused.status_code == 401
    assert client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_refresh},
    ).status_code == 401
    assert client.get(
        "/api/v1/auth/session",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    ).status_code == 401

    with sessions() as db:
        rows = db.query(RefreshToken).filter(RefreshToken.user_id == "target").all()
        assert len(rows) == 2
        assert all(row.revoked_at is not None for row in rows)
        assert all(first_refresh != row.token_hash for row in rows)
        assert db.query(AuditLog).filter(
            AuditLog.entity_id == "target",
            AuditLog.action == "refresh_token_reuse_detected",
        ).count() == 1


def test_mfa_setup_login_recovery_code_and_disable(security_context):
    client, sessions = security_context
    token = login(client, "admin@example.com", "AdminPassword123")
    headers = {"Authorization": f"Bearer {token}"}
    setup = client.post(
        "/api/v1/auth/mfa/setup",
        headers=headers,
        json={"current_password": "AdminPassword123"},
    )
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")
    code = mfa_service._totp(secret, int(time.time()) // 30)
    confirmed = client.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": code})
    assert confirmed.status_code == 200
    recovery_codes = confirmed.json()["recovery_codes"]
    assert len(recovery_codes) == 8
    assert client.get("/api/v1/auth/session", headers=headers).status_code == 401

    challenge = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123"},
    ).json()
    assert challenge["mfa_required"] is True
    assert challenge["access_token"] is None
    verified = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": challenge["mfa_challenge_token"], "code": recovery_codes[0]},
    )
    assert verified.status_code == 200
    mfa_headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}
    assert client.get("/api/v1/auth/session", headers=mfa_headers).status_code == 200

    with sessions() as db:
        user = db.query(User).filter(User.id == "admin").one()
        assert user.mfa_secret_encrypted != secret
        assert recovery_codes[0] not in (user.mfa_recovery_hashes or "")

    disabled = client.post(
        "/api/v1/auth/mfa/disable",
        headers=mfa_headers,
        json={"current_password": "AdminPassword123", "code": recovery_codes[1]},
    )
    assert disabled.status_code == 200
    signed_in = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPassword123"},
    ).json()
    assert signed_in["mfa_required"] is False
    assert signed_in["access_token"]


def test_forgot_response_does_not_reveal_account_and_token_is_single_use(security_context):
    client, sessions = security_context
    existing = client.post("/api/v1/auth/password/forgot", json={"email": "admin@example.com"})
    missing = client.post("/api/v1/auth/password/forgot", json={"email": "missing@example.com"})
    assert existing.status_code == missing.status_code == 200
    assert existing.json() == missing.json()
    with sessions() as db:
        assert db.query(PasswordResetToken).count() == 1
        raw_token = auth_service.issue_reset_token(db, "admin@example.com")
        payload = PasswordResetRequest(token=raw_token, new_password="Recovered password 2026", confirm_password="Recovered password 2026")
        auth_service.reset_password(db, payload)
        with pytest.raises(Exception, match="Token inválido o vencido"):
            auth_service.reset_password(db, payload)
    login(client, "admin@example.com", "Recovered password 2026")


def test_admin_reset_and_email_correction_are_scoped_and_audited(security_context):
    client, sessions = security_context
    token = login(client, "admin@example.com", "AdminPassword123")
    headers = {"Authorization": f"Bearer {token}"}
    denied = client.post("/api/v1/security/admin/projects/project/users/target/password-reset", headers=headers, json={"admin_password": "incorrecta"})
    assert denied.status_code == 401
    outside = client.post("/api/v1/security/admin/projects/project/users/outsider/password-reset", headers=headers, json={"admin_password": "AdminPassword123"})
    assert outside.status_code == 404
    reset = client.post("/api/v1/security/admin/projects/project/users/target/password-reset", headers=headers, json={"admin_password": "AdminPassword123"})
    assert reset.status_code == 200
    temporary = reset.json()["temporary_password"]
    assert len(temporary) == 20
    target_token = login(client, "target@example.com", temporary)
    session = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {target_token}"})
    assert session.json()["must_change_password"] is True
    updated = client.patch("/api/v1/security/admin/projects/project/users/target/email", headers=headers, json={"email": "CORREGIDO@example.com", "admin_password": "AdminPassword123"})
    assert updated.status_code == 200
    assert updated.json()["email"] == "corregido@example.com"
    with sessions() as db:
        target = db.query(User).filter(User.id == "target").one()
        target.mfa_enabled = True
        target.mfa_secret_encrypted = "encrypted-placeholder"
        target.mfa_recovery_hashes = "[]"
        db.commit()
    mfa_reset = client.post(
        "/api/v1/security/admin/projects/project/users/target/mfa-reset",
        headers=headers,
        json={"admin_password": "AdminPassword123"},
    )
    assert mfa_reset.status_code == 200
    with sessions() as db:
        logs = db.query(AuditLog).filter(AuditLog.entity_id == "target").all()
        assert {log.action for log in logs} == {"admin_password_reset", "admin_email_update", "admin_mfa_reset"}
        assert all(temporary not in (log.after_json or "") for log in logs)
        target = db.query(User).filter(User.id == "target").one()
        assert target.mfa_enabled is False
        assert target.mfa_secret_encrypted is None
