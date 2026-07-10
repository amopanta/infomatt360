from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.files import FileAsset
from app.models.identity import Project, User
from app.models.runtime_record import RuntimeRecord


def test_dashboard_summary_is_project_scoped():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="dashboard-user", full_name="Dashboard", document_id="dash-doc", email="dash@example.com", password_hash=hash_password("DashboardPassword123"))
        project = Project(id="dashboard-project", name="Proyecto")
        other = Project(id="other-project", name="Otro")
        template = BuilderTemplate(id="dashboard-template", project_id=project.id, name="Encuesta", status="published")
        db.add_all([
            user, project, other, template,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
            RuntimeRecord(id="record-1", project_id=project.id, template_id=template.id, status="submitted", submitted_by=user.id),
            FileAsset(id="file-1", project_id=project.id, asset_type="image", original_name="foto.jpg", storage_path="uploads/foto.jpg", size_bytes=2048),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": "dash@example.com", "password": "DashboardPassword123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            response = client.get("/api/v1/dashboard/projects/dashboard-project/summary", headers=headers)
            assert response.status_code == 200
            assert response.json()["templates_total"] == 1
            assert response.json()["published_templates"] == 1
            assert response.json()["records_total"] == 1
            assert response.json()["records_by_status"] == {"submitted": 1}
            assert response.json()["users_total"] == 1
            assert response.json()["files_total"] == 1
            assert response.json()["storage_bytes"] == 2048
            assert response.json()["recent_records"][0]["template_name"] == "Encuesta"
            assert client.get("/api/v1/dashboard/projects/other-project/summary", headers=headers).status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
