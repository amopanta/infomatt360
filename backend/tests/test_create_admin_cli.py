"""Comando para crear o recuperar un administrador desde el servidor."""

from starlette.testclient import TestClient

from app.cli.create_admin import create_or_recover, password_problem
from app.db.base import Base
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import Role, User
from test_form_assignments_reopening import auth, setup_client


def test_password_rules():
    assert password_problem("corta1") is not None
    assert password_problem("sololetrasaqui") is not None
    assert password_problem("Valida12345") is None


def test_creates_admin_that_can_log_in_and_recovers_existing_account():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            result = create_or_recover(db, "Responsable@Ejemplo.com", "Persona Responsable", "123", "Nueva12345x", None)
            assert result["created"] is True and result["projects"]
        with sessions() as db:
            user = db.query(User).filter(User.email == "responsable@ejemplo.com").one()
            role = db.query(Role).filter(Role.name == "Administrador").one()
            assert "identity.users.manage" in role.permissions.split(",")
            assert db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == user.id, UserProjectAssignment.role_id == role.id).count() == len(result["projects"])
            assert db.query(AuditLog).filter(AuditLog.action == "admin_created_cli").count() == 1
        with TestClient(app) as client:
            assert auth(client, "responsable@ejemplo.com", "Nueva12345x")["Authorization"].startswith("Bearer ")

        # Cuenta existente desactivada: recupera acceso con contraseña nueva.
        with sessions() as db:
            existing = db.query(User).filter(User.email == "assign-owner@example.com").one()
            existing.status = "inactive"
            db.commit()
            again = create_or_recover(db, "assign-owner@example.com", "", None, "Otra123456x", None)
            assert again["created"] is False
        with TestClient(app) as client:
            assert auth(client, "assign-owner@example.com", "Otra123456x")["Authorization"].startswith("Bearer ")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
