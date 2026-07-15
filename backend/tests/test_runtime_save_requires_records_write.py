"""Regresion del hallazgo S-001 de la auditoria tecnica de julio 2026:
POST /runtime/save solo validaba acceso al proyecto (user_has_project_access),
no el permiso records.write en si -- un usuario con un rol de solo lectura
podia guardar registros. Ver backend/app/api/v1/runtime.py.
"""

from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.identity import Project, Role, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="s001-project", name="Proyecto S-001")
        template = BuilderTemplate(id="s001-template", project_id=project.id, name="Plantilla", status="published")
        writer = User(id="s001-writer", full_name="Capturista", document_id="s001-writer-doc", email="s001-writer@example.com", password_hash=hash_password("Writer12345!"))
        reader = User(id="s001-reader", full_name="Solo lectura", document_id="s001-reader-doc", email="s001-reader@example.com", password_hash=hash_password("Reader12345!"))
        writer_role = Role(id="s001-writer-role", name="Capturista", permissions="records.write,records.read")
        reader_role = Role(id="s001-reader-role", name="Solo lectura", permissions="records.read")
        db.add_all([
            project, template, writer, reader, writer_role, reader_role,
            UserProjectAssignment(user_id=writer.id, project_id=project.id, role_id=writer_role.id, status="active"),
            UserProjectAssignment(user_id=reader.id, project_id=project.id, role_id=reader_role.id, status="active"),
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


def test_read_only_user_cannot_save_runtime_record():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            reader_headers = auth(client, "s001-reader@example.com", "Reader12345!")
            denied = client.post(
                "/api/v1/runtime/save", headers=reader_headers,
                json={"project_id": "s001-project", "template_id": "s001-template", "values": []},
            )
            assert denied.status_code == 403

            writer_headers = auth(client, "s001-writer@example.com", "Writer12345!")
            allowed = client.post(
                "/api/v1/runtime/save", headers=writer_headers,
                json={"project_id": "s001-project", "template_id": "s001-template", "values": []},
            )
            assert allowed.status_code == 200, allowed.text
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
