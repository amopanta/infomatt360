from io import BytesIO
from zipfile import ZipFile

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
from app.models.identity import Project, User
from app.models.runtime_record import RuntimeRecord


def test_report_summary_is_project_scoped_and_groups_records():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        user = User(id="report-user", full_name="Report User", document_id="report-doc", email="report@example.com", password_hash=hash_password("ReportPassword123"))
        project = Project(id="report-project", name="Proyecto reportes")
        other = Project(id="report-other", name="Otro")
        template_a = BuilderTemplate(id="report-template-a", project_id=project.id, name="Encuesta A", status="published")
        template_b = BuilderTemplate(id="report-template-b", project_id=project.id, name="Encuesta B", status="draft")
        other_template = BuilderTemplate(id="report-template-other", project_id=other.id, name="Encuesta Otro", status="published")
        db.add_all([
            user,
            project,
            other,
            template_a,
            template_b,
            other_template,
            UserProjectAssignment(user_id=user.id, project_id=project.id, status="active"),
            RuntimeRecord(id="record-a-1", project_id=project.id, template_id=template_a.id, status="submitted", submitted_by=user.id),
            RuntimeRecord(id="record-a-2", project_id=project.id, template_id=template_a.id, status="approved", submitted_by=user.id),
            RuntimeRecord(id="record-other", project_id=other.id, template_id=other_template.id, status="submitted", submitted_by=user.id),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": "report@example.com", "password": "ReportPassword123"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            response = client.get("/api/v1/reports/project/report-project/summary", headers=headers)
            exported = client.get("/api/v1/reports/project/report-project/summary.xlsx", headers=headers)
            forbidden = client.get("/api/v1/reports/project/report-other/summary", headers=headers)

            assert response.status_code == 200
            payload = response.json()
            assert payload["records_total"] == 2
            assert payload["records_by_status"] == {"approved": 1, "submitted": 1}
            assert [item["template_id"] for item in payload["templates"]] == ["report-template-a", "report-template-b"]
            assert payload["templates"][0]["records_total"] == 2
            assert payload["templates"][0]["percent_of_total"] == 100
            assert payload["templates"][1]["records_total"] == 0
            assert exported.status_code == 200
            assert exported.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with ZipFile(BytesIO(exported.content)) as xlsx:
                names = set(xlsx.namelist())
                assert "xl/workbook.xml" in names
                assert "xl/worksheets/sheet1.xml" in names
                assert "xl/worksheets/sheet3.xml" in names
                assert "Encuesta A" in xlsx.read("xl/worksheets/sheet3.xml").decode("utf-8")
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
