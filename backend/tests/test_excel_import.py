from io import BytesIO

from openpyxl import Workbook
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
from app.models.participants import Participant


def _build_xlsx(headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="excel-project", name="Excel Project")
        admin_role = Role(id="excel-admin-role", name="Admin Excel", permissions="identity.users.manage")
        basic_role = Role(id="excel-basic-role", name="Basico", permissions="records.read")
        admin = User(id="excel-admin", full_name="Admin", document_id="excel-admin-doc", email="excel-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="excel-basic", full_name="Basic", document_id="excel-basic-doc", email="excel-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            admin_role,
            basic_role,
            admin,
            basic,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
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


def test_excel_import_full_flow_with_auto_mapping_and_duplicate_report():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")
            basic_headers = auth(client, "excel-basic@example.com", "Basic12345!")

            content = _build_xlsx(
                ["Nombre", "Documento"],
                [
                    ["Ana Gomez", "CC-1"],
                    ["Ana Duplicada", "CC-1"],
                    ["Beatriz Ruiz", "CC-2"],
                ],
            )

            denied = client.post(
                "/api/v1/excel-import/upload",
                headers=basic_headers,
                data={"project_id": "excel-project", "entity_type": "participants"},
                files={"upload": ("participantes.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert denied.status_code == 403

            uploaded = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "participants"},
                files={"upload": ("participantes.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert uploaded.status_code == 200
            job = uploaded.json()
            assert job["status"] == "uploaded"
            assert job["total_rows"] == 3
            assert job["column_mapping"] == {"Nombre": "full_name", "Documento": "document_id"}
            assert job["preview"]["sample_rows"][0] == {"Nombre": "Ana Gomez", "Documento": "CC-1"}
            job_id = job["id"]

            mapped = client.patch(
                f"/api/v1/excel-import/{job_id}/mapping",
                headers=admin_headers,
                json={"column_mapping": job["column_mapping"]},
            )
            assert mapped.status_code == 200
            assert mapped.json()["status"] == "mapped"

            approved = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            assert approved.status_code == 200
            result = approved.json()
            assert result["status"] == "completed"
            assert result["imported_rows"] == 2
            assert result["failed_rows"] == 1
            assert "CC-1" in result["error_report"][0]["error"] or "documento" in result["error_report"][0]["error"].lower()

            with sessions() as db:
                participants = db.query(Participant).filter(Participant.project_id == "excel-project").all()
                assert {p.document_id for p in participants} == {"CC-1", "CC-2"}

            second_approve = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            assert second_approve.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_rejects_unsupported_entity_type():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")
            content = _build_xlsx(["Nombre"], [["Ana"]])
            response = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "inventario"},
                files={"upload": ("archivo.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
