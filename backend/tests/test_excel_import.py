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
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


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
        newmember = User(id="excel-newmember", full_name="Nuevo Miembro", document_id="excel-newmember-doc", email="excel-newmember@example.com", password_hash=hash_password("Newmember12345!"))
        template = BuilderTemplate(id="excel-records-template", project_id=project.id, name="Plantilla de registros", status="published")
        db.add_all([
            project,
            admin_role,
            basic_role,
            admin,
            basic,
            newmember,
            template,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
            BuilderComponent(id="excel-comp-nombre", template_id=template.id, component_type="TEXT", name="nombre", label="Nombre", sort_order=1),
            BuilderComponent(id="excel-comp-integrantes", template_id=template.id, component_type="NUMBER", name="integrantes", label="Integrantes", sort_order=2),
            BuilderComponent(id="excel-comp-fecha", template_id=template.id, component_type="DATE", name="fecha_visita", label="Fecha de visita", sort_order=3),
            BuilderComponent(id="excel-comp-documento", template_id=template.id, component_type="DOCUMENT_ID", name="documento", label="Documento", sort_order=4),
            BuilderComponent(id="excel-comp-ubicacion", template_id=template.id, component_type="GPS", name="ubicacion", label="Ubicación", sort_order=5),
            Participant(id="excel-participant-1", project_id=project.id, document_id="CC-9", full_name="Participante Existente"),
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
                # CC-9 viene del fixture compartido de setup_client() (participante
                # preexistente usado por las pruebas de carga de registros).
                assert {p.document_id for p in participants} == {"CC-1", "CC-2", "CC-9"}

            second_approve = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            assert second_approve.status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_assignments_creates_project_role_assignment_and_reports_lookup_failures():
    """Carga masiva de asignaciones usuario-proyecto-rol (ver docs/103) --
    cierra el hallazgo #2 de la auditoria de trazabilidad (docs/96)."""
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")

            content = _build_xlsx(
                ["Correo", "Rol"],
                [
                    ["excel-newmember@example.com", "Basico"],
                    ["no-existe@example.com", "Basico"],
                    ["excel-basic@example.com", "Rol Fantasma"],
                ],
            )

            uploaded = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "assignments"},
                files={"upload": ("asignaciones.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert uploaded.status_code == 200
            job = uploaded.json()
            assert job["column_mapping"] == {"Correo": "email", "Rol": "role_name"}
            job_id = job["id"]

            client.patch(f"/api/v1/excel-import/{job_id}/mapping", headers=admin_headers, json={"column_mapping": job["column_mapping"]})
            approved = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            assert approved.status_code == 200
            result = approved.json()
            assert result["imported_rows"] == 1
            assert result["failed_rows"] == 2
            errors = " ".join(item["error"].lower() for item in result["error_report"])
            assert "no existe un usuario" in errors
            assert "no existe un rol" in errors

            with sessions() as db:
                new_assignment = db.query(UserProjectAssignment).filter(
                    UserProjectAssignment.user_id == "excel-newmember",
                    UserProjectAssignment.project_id == "excel-project",
                ).first()
                assert new_assignment is not None
                assert new_assignment.role_id == "excel-basic-role"
                assert new_assignment.status == "active"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_records_requires_template_id():
    """Carga masiva de registros historicos (ver docs/104) -- cierra el
    hallazgo #3 de la auditoria de trazabilidad (docs/96)."""
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")
            content = _build_xlsx(["Nombre"], [["Ana"]])
            response = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "records"},
                files={"upload": ("registros.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_records_target_fields_exclude_unsupported_types():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")
            content = _build_xlsx(["Nombre"], [["Ana"]])
            uploaded = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "records", "template_id": "excel-records-template"},
                files={"upload": ("registros.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert uploaded.status_code == 200
            job = uploaded.json()
            field_names = {field["name"] for field in job["target_fields"]}
            assert field_names == {"nombre", "integrantes", "fecha_visita", "documento", "_meta_status", "_meta_created_at"}
            assert "ubicacion" not in field_names  # GPS excluido, no es un tipo escalar simple
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_records_creates_real_records_with_types_historical_date_and_participant_link():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")

            # "Fecha" (no "Fecha de visita", que es la etiqueta del campo DATE real
            # de la plantilla) es el alias que mapea al campo reservado de fecha
            # historica -- distinto del campo de formulario "fecha_visita".
            content = _build_xlsx(
                ["Nombre", "Integrantes", "Fecha", "Documento"],
                [
                    ["Hogar Historico", 4, "2020-03-15", "CC-9"],  # con fecha historica y enlace a participante existente
                    ["Hogar Sin Fecha", 2, "", ""],  # sin fecha historica, sin documento
                ],
            )

            uploaded = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "records", "template_id": "excel-records-template"},
                files={"upload": ("registros.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert uploaded.status_code == 200
            job = uploaded.json()
            assert job["column_mapping"] == {
                "Nombre": "nombre",
                "Integrantes": "integrantes",
                "Fecha": "_meta_created_at",
                "Documento": "documento",
            }
            job_id = job["id"]

            client.patch(f"/api/v1/excel-import/{job_id}/mapping", headers=admin_headers, json={"column_mapping": job["column_mapping"]})
            approved = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            assert approved.status_code == 200
            result = approved.json()
            assert result["imported_rows"] == 2
            assert result["failed_rows"] == 0

            with sessions() as db:
                records = db.query(RuntimeRecord).filter(RuntimeRecord.template_id == "excel-records-template").order_by(RuntimeRecord.created_at).all()
                assert len(records) == 2

                historical = next(r for r in records if r.participant_id is not None)
                assert historical.participant_id == "excel-participant-1"
                assert historical.created_at.strftime("%Y-%m-%d") == "2020-03-15"

                no_date = next(r for r in records if r.participant_id is None)
                assert no_date.created_at.strftime("%Y-%m-%d") != "2020-03-15"

                integrantes_value = db.query(RuntimeRecordValue).filter(
                    RuntimeRecordValue.record_id == historical.id,
                    RuntimeRecordValue.field_name == "integrantes",
                ).first()
                assert integrantes_value.field_value_json == "4"  # JSON numero, no string
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_excel_import_records_empty_row_is_reported_as_error():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin_headers = auth(client, "excel-admin@example.com", "Admin12345!")
            # "Columna sin mapeo" no coincide con ningun alias de campo -- la fila
            # llega a aprobacion sin ningun valor mapeado, aunque tenga contenido.
            content = _build_xlsx(["Columna sin mapeo"], [["algun valor"]])
            uploaded = client.post(
                "/api/v1/excel-import/upload",
                headers=admin_headers,
                data={"project_id": "excel-project", "entity_type": "records", "template_id": "excel-records-template"},
                files={"upload": ("registros.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            job = uploaded.json()
            assert job["total_rows"] == 1
            job_id = job["id"]
            client.patch(f"/api/v1/excel-import/{job_id}/mapping", headers=admin_headers, json={"column_mapping": job["column_mapping"]})
            approved = client.post(f"/api/v1/excel-import/{job_id}/approve", headers=admin_headers)
            result = approved.json()
            assert result["imported_rows"] == 0
            assert result["failed_rows"] == 1
            assert "ningun valor" in result["error_report"][0]["error"].lower()
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
