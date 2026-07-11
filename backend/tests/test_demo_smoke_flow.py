from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.cli.seed_demo import DEMO_EMAIL, DEMO_PASSWORD, DEMO_PROJECT_ID, DEMO_TEMPLATE_ID, seed
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def test_demo_seed_supports_end_to_end_api_smoke_flow():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
            assert login.status_code == 200
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            session = client.get("/api/v1/auth/session", headers=headers)
            dashboard = client.get(f"/api/v1/dashboard/projects/{DEMO_PROJECT_ID}/summary", headers=headers)
            templates = client.get(f"/api/v1/builder/templates/{DEMO_PROJECT_ID}", headers=headers)
            records = client.get(f"/api/v1/runtime/template/{DEMO_TEMPLATE_ID}/records/search?limit=10", headers=headers)
            report = client.get(f"/api/v1/reports/project/{DEMO_PROJECT_ID}/summary", headers=headers)
            report_xlsx = client.get(f"/api/v1/reports/project/{DEMO_PROJECT_ID}/summary.xlsx", headers=headers)
            map_response = client.get(f"/api/v1/gis/map/{DEMO_PROJECT_ID}", headers=headers)
            audit = client.get(f"/api/v1/audit/?project_id={DEMO_PROJECT_ID}", headers=headers)

            assert session.status_code == 200
            assert session.json()["email"] == DEMO_EMAIL
            assert any(project["id"] == DEMO_PROJECT_ID for project in session.json()["projects"])
            assert dashboard.status_code == 200
            assert dashboard.json()["records_total"] == 3
            assert templates.status_code == 200
            assert templates.json()[0]["id"] == DEMO_TEMPLATE_ID
            assert records.status_code == 200
            assert records.json()["total"] == 3
            assert report.status_code == 200
            assert report.json()["records_total"] == 3
            assert report_xlsx.status_code == 200
            with ZipFile(BytesIO(report_xlsx.content)) as archive:
                assert "xl/workbook.xml" in archive.namelist()
            assert map_response.status_code == 200
            assert len(map_response.json()["features"]) >= 3
            assert audit.status_code == 200
            assert any(item["action"] == "demo_seed" for item in audit.json())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
