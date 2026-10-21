"""H11: barrido de acceso cruzado entre proyectos.

Un usuario con todos los permisos en el proyecto A (salvo organizations.manage,
que es de plataforma: crea y lista todas las organizaciones, docs/60), y
ninguno en B, llama
cada ruta GET del API con identificadores de B (en la ruta y como parámetro
de consulta). Ninguna respuesta puede contener datos de B: todos sus textos
llevan la marca SECRETO-B.
"""

import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.permissions import ALL_PERMISSIONS, ORGANIZATIONS_MANAGE
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.models.case_management import CaseEvent, ParticipantCase, SavedExport
from app.models.device_status import FieldDeviceStatus, FieldRoutePoint
from app.models.files import FileAsset
from app.models.gestor_team import GestorTeam, GestorTeamUser
from app.models.gis import GisFeature, GisLayer
from app.models.identity import Project, Role, User
from app.models.organization import Organization
from app.models.participants import Participant
from app.models.review import ReviewObservation
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.core.time import utc_now

MARK = "SECRETO-B"
B_IDS = {
    "project_id": "proj-b", "template_id": "tpl-b", "record_id": "rec-b", "participant_id": "part-b",
    "file_id": "file-b", "case_id": "case-b", "team_id": "team-b", "export_id": "exp-b",
    "organization_id": "org-b", "page_id": "page-b", "section_id": "sec-b", "row_id": "row-b",
    "item_id": "x-b", "field_name": "nombre", "observation_id": "obs-b",
}

# Rutas que devuelven a propósito datos de catálogo o del propio usuario, no de un proyecto.
NOT_PROJECT_SCOPED: set[str] = set()


def _seed(db):
    now = utc_now()
    db.add_all([
        Organization(id="org-a", name="Org A", slug="org-a"),
        Organization(id="org-b", name=f"ORG {MARK}", slug="org-b"),
        Project(id="proj-a", name="Proyecto A", organization_id="org-a"),
        Project(id="proj-b", name=f"Proyecto {MARK}", organization_id="org-b"),
        Role(id="role-all", name="Todo", permissions=",".join(sorted(ALL_PERMISSIONS - {ORGANIZATIONS_MANAGE}))),
        User(id="user-a", full_name="Usuario A", document_id="A1", email="a@example.com", password_hash=hash_password("Clave12345!")),
        User(id="user-b", full_name=f"Gestor {MARK}", document_id="B1", email="b@example.com", password_hash=hash_password("Clave12345!")),
        UserProjectAssignment(user_id="user-a", project_id="proj-a", role_id="role-all", status="active"),
        UserProjectAssignment(user_id="user-b", project_id="proj-b", role_id="role-all", status="active"),
        BuilderTemplate(id="tpl-b", project_id="proj-b", name=f"Plantilla {MARK}", status="published"),
        BuilderPage(id="page-b", template_id="tpl-b", title=f"Página {MARK}", sort_order=1, visible="true"),
        BuilderSection(id="sec-b", page_id="page-b", title=f"Sección {MARK}", sort_order=1, visible="true", collapsible="false"),
        BuilderRow(id="row-b", section_id="sec-b", sort_order=1, responsive="true"),
        BuilderColumn(id="col-b", row_id="row-b", desktop_width=12, tablet_width=12, mobile_width=12, sort_order=1),
        BuilderComponent(id="cmp-b", template_id="tpl-b", column_id="col-b", component_type="TEXT", name="nombre", label=f"Pregunta {MARK}", sort_order=1),
        Participant(id="part-b", project_id="proj-b", full_name=f"Persona {MARK}", document_id="9999"),
        RuntimeRecord(id="rec-b", project_id="proj-b", template_id="tpl-b", participant_id="part-b", status="submitted", submitted_by="user-b"),
        RuntimeRecordValue(id="val-b", record_id="rec-b", field_name="nombre", field_value_json=f'"Valor {MARK}"'),
        FileAsset(id="file-b", project_id="proj-b", record_id="rec-b", participant_id="part-b", asset_type="PDF",
                  original_name=f"archivo-{MARK}.pdf", storage_path="/no/existe.pdf", size_bytes=10),
        ParticipantCase(id="case-b", project_id="proj-b", participant_id="part-b", title=f"Caso {MARK}", created_by="user-b",
                        created_at=now, updated_at=now),
        CaseEvent(id="evt-b", case_id="case-b", event_type="note", from_user_id="user-b", created_at=now),
        GestorTeam(id="team-b", project_id="proj-b", name=f"Equipo {MARK}", created_by="user-b"),
        GestorTeamUser(team_id="team-b", user_id="user-b"),
        SavedExport(id="exp-b", project_id="proj-b", name=f"Exportación {MARK}", recipient_user_id="user-b"),
        ReviewObservation(id="obs-b", project_id="proj-b", record_id="rec-b", field_name="nombre", reason=f"Observación {MARK}", created_by="user-b"),
        GisLayer(id="layer-b", project_id="proj-b", name=f"Capa {MARK}", layer_type="points", status="active"),
        GisFeature(id="feat-b", project_id="proj-b", layer_id="layer-b", record_id="rec-b", feature_type="Point",
                   latitude="4.6", longitude="-74.0", status="active"),
        FieldDeviceStatus(id="dev-b", device_id="device-b", user_id="user-b", project_id="proj-b", device_name=f"Tablet {MARK}"),
        FieldRoutePoint(id="pt-b", device_id="device-b", user_id="user-b", project_id="proj-b", latitude=4.6, longitude=-74.0, recorded_at=now),
    ])
    db.commit()


def _fill(path: str) -> str:
    return re.sub(r"{(\w+)}", lambda m: B_IDS.get(m.group(1), "x-b"), path)


def scan_leaks(email: str = "a@example.com") -> list[str]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    leaks: list[str] = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            token = client.post("/api/v1/auth/login", json={"email": email, "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}", "X-Project-Id": "proj-b"}
            query = {"project_id": "proj-b", "template_id": "tpl-b", "participant_id": "part-b", "record_id": "rec-b",
                     "date_from": "2000-01-01T00:00:00Z", "date_to": "2100-01-01T00:00:00Z"}
            for path, operations in sorted(app.openapi()["paths"].items()):
                if "get" not in operations or path in NOT_PROJECT_SCOPED:
                    continue
                response = client.get(_fill(path), headers=headers, params=query)
                if response.status_code < 300 and MARK in response.text:
                    leaks.append(f"{response.status_code} GET {path}")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
    return leaks


def test_scan_detects_data_when_access_is_legit():
    """Control positivo: el dueño de B sí ve sus datos en muchas rutas (si no, el barrido no mide nada)."""
    assert len(scan_leaks("b@example.com")) >= 25


def test_no_get_route_returns_another_projects_data():
    leaks = scan_leaks()
    assert leaks == [], "Rutas que entregan datos de otro proyecto:\n" + "\n".join(leaks)


def test_branding_of_another_organization_cannot_be_changed():
    """Antes bastaba organizations.branding.manage en cualquier proyecto para
    cambiar el logo y el nombre de otra organización."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            token = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            body = {"organization_name": "Tomada", "primary_color": "#000000"}
            assert client.put("/api/v1/organizations/org-b/branding", headers=headers, json=body).status_code == 403
            assert client.get("/api/v1/organizations/org-b/branding", headers=headers).status_code == 403
            assert client.post("/api/v1/organizations/org-b/branding/logo", headers=headers,
                               files={"upload": ("logo.png", b"PNG", "image/png")}).status_code == 403
            assert client.put("/api/v1/organizations/org-a/branding", headers=headers, json=body).status_code == 200
            with sessions() as db:
                assert db.get(Organization, "org-b").name == f"ORG {MARK}"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
