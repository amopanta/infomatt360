from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import Project, User


def test_audit_list_is_project_scoped_and_includes_created_at():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="audit-user", full_name="Audit User", document_id="audit-doc", email="audit@example.com", password_hash=hash_password("AuditPassword123"))
        project = Project(id="audit-project", name="Auditable")
        other = Project(id="audit-other", name="Otro")
        db.add_all([
            user,
            project,
            other,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
            AuditLog(id="audit-visible", user_id=user.id, project_id=project.id, module="identity", action="admin_password_reset", entity_type="user", entity_id=user.id),
            AuditLog(id="audit-hidden", user_id="someone", project_id=other.id, module="identity", action="admin_password_reset", entity_type="user", entity_id="someone"),
            AuditLog(id="audit-personal", user_id=user.id, project_id=None, module="identity", action="self_password_change", entity_type="user", entity_id=user.id),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": "audit@example.com", "password": "AuditPassword123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            project_response = client.get("/api/v1/audit/?project_id=audit-project", headers=headers)
            personal_response = client.get("/api/v1/audit/", headers=headers)
            forbidden = client.get("/api/v1/audit/?project_id=audit-other", headers=headers)

            assert project_response.status_code == 200
            assert [item["id"] for item in project_response.json()] == ["audit-visible"]
            assert project_response.json()[0]["created_at"]
            assert personal_response.status_code == 200
            assert [item["id"] for item in personal_response.json()] == ["audit-personal"]
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
