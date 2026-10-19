"""H11: barrido de acceso territorial dentro de un mismo proyecto.

Un coordinador limitado a Cundinamarca / Soacha (con todos los permisos de
proyecto salvo gestionar usuarios, que no tiene restricción territorial)
llama cada ruta GET apuntando a un participante de Bogotá y a todo lo que
cuelga de él. Nada de eso puede aparecer: sus textos llevan FUERA-TERR.
"""

import json
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.permissions import ALL_PERMISSIONS, IDENTITY_USERS_MANAGE, ORGANIZATIONS_MANAGE
from app.core.security import hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.models.ai import AiCheck
from app.models.case_management import CaseEvent, ParticipantCase, UserTerritory
from app.models.files import FileAsset
from app.models.gis import GisFeature, GisLayer
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

MARK = "FUERA-TERR"
IDS = {"project_id": "proj-t", "template_id": "tpl-t", "record_id": "rec-out", "participant_id": "p-out",
       "file_id": "file-out", "case_id": "case-out", "page_id": "page-t", "section_id": "sec-t", "row_id": "row-t",
       "field_name": "nombre"}


def _seed(db):
    now = utc_now()
    field_perms = ALL_PERMISSIONS - {IDENTITY_USERS_MANAGE, ORGANIZATIONS_MANAGE}
    meta = lambda dep, mun: json.dumps({"department": dep, "municipality": mun})
    db.add_all([
        Project(id="proj-t", name="Proyecto territorial"),
        Role(id="role-coord", name="Coordinador", permissions=",".join(sorted(field_perms))),
        Role(id="role-admin", name="Admin", permissions=",".join(sorted(field_perms | {IDENTITY_USERS_MANAGE}))),
        User(id="coord", full_name="Coordinador Soacha", document_id="C1", email="coord@example.com", password_hash=hash_password("Clave12345!")),
        User(id="admin", full_name="Admin proyecto", document_id="A1", email="admin@example.com", password_hash=hash_password("Clave12345!")),
        UserProjectAssignment(user_id="coord", project_id="proj-t", role_id="role-coord", status="active"),
        UserProjectAssignment(user_id="admin", project_id="proj-t", role_id="role-admin", status="active"),
        UserTerritory(project_id="proj-t", user_id="coord", department="Cundinamarca", municipality="Soacha"),
        BuilderTemplate(id="tpl-t", project_id="proj-t", name="Visita", status="published"),
        BuilderPage(id="page-t", template_id="tpl-t", title="P", sort_order=1, visible="true"),
        BuilderSection(id="sec-t", page_id="page-t", title="S", sort_order=1, visible="true", collapsible="false"),
        BuilderRow(id="row-t", section_id="sec-t", sort_order=1, responsive="true"),
        BuilderColumn(id="col-t", row_id="row-t", desktop_width=12, tablet_width=12, mobile_width=12, sort_order=1),
        BuilderComponent(id="cmp-t", template_id="tpl-t", column_id="col-t", component_type="TEXT", name="nombre", label="Nombre", sort_order=1),
        Participant(id="p-in", project_id="proj-t", full_name="Persona de Soacha", document_id="1001", metadata_json=meta("Cundinamarca", "Soacha")),
        Participant(id="p-out", project_id="proj-t", full_name=f"Persona {MARK}", document_id="2002", metadata_json=meta("Bogotá D.C.", "Bogotá")),
        RuntimeRecord(id="rec-in", project_id="proj-t", template_id="tpl-t", participant_id="p-in", status="submitted", submitted_by="admin"),
        RuntimeRecordValue(id="val-in", record_id="rec-in", field_name="nombre", field_value_json='"Valor de Soacha"'),
        RuntimeRecord(id="rec-out", project_id="proj-t", template_id="tpl-t", participant_id="p-out", status="submitted", submitted_by="admin"),
        RuntimeRecordValue(id="val-out", record_id="rec-out", field_name="nombre", field_value_json=f'"Valor {MARK}"'),
        FileAsset(id="file-out", project_id="proj-t", record_id="rec-out", participant_id="p-out", asset_type="PDF",
                  original_name=f"archivo-{MARK}.pdf", storage_path="/no/existe.pdf", size_bytes=10),
        ParticipantCase(id="case-out", project_id="proj-t", participant_id="p-out", title=f"Caso {MARK}", created_by="admin", created_at=now, updated_at=now),
        CaseEvent(id="evt-out", case_id="case-out", event_type="note", from_user_id="admin", created_at=now),
        GisLayer(id="layer-t", project_id="proj-t", name="Capa", layer_type="points", status="active"),
        GisFeature(id="feat-out", project_id="proj-t", layer_id="layer-t", record_id="rec-out", feature_type="Point",
                   latitude="4.6", longitude="-74.0", status="active", properties_json=json.dumps({"nombre": f"Punto {MARK}"})),
        AiCheck(id="ai-out", project_id="proj-t", record_id="rec-out", check_type="quality", status="done",
                result_json=json.dumps({"resumen": f"Revisión {MARK}"}), created_by="admin"),
    ])
    db.commit()


def scan(email: str) -> list[str]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    hits: list[str] = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            token = client.post("/api/v1/auth/login", json={"email": email, "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            query = {"project_id": "proj-t", "template_id": "tpl-t", "participant_id": "p-out", "record_id": "rec-out",
                     "date_from": "2000-01-01T00:00:00Z", "date_to": "2100-01-01T00:00:00Z"}
            for path, operations in sorted(app.openapi()["paths"].items()):
                if "get" not in operations:
                    continue
                url = re.sub(r"{(\w+)}", lambda m: IDS.get(m.group(1), "x"), path)
                response = client.get(url, headers=headers, params=query)
                if response.status_code < 300 and MARK in response.text:
                    hits.append(f"{response.status_code} GET {path}")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
    return hits


def test_scan_sees_outside_data_for_unrestricted_admin():
    assert len(scan("admin@example.com")) >= 10


def test_no_get_route_reveals_participants_outside_the_users_territory():
    hits = scan("coord@example.com")
    assert hits == [], "Rutas que muestran datos fuera del territorio:\n" + "\n".join(hits)


OUT_VALUES = {"p-out", "rec-out", "file-out", "case-out", "evt-out", "feat-out", "val-out"}


def _snapshot_out(engine) -> dict[str, list]:
    from sqlalchemy import inspect, text
    out: dict[str, list] = {}
    with engine.connect() as conn:
        for table in inspect(engine).get_table_names():
            columns = {c["name"] for c in inspect(engine).get_columns(table)}
            keys = [c for c in ("id", "participant_id", "record_id", "case_id") if c in columns]
            if not keys:
                continue
            rows = conn.execute(text(f'SELECT * FROM "{table}"')).mappings().all()
            mine = [dict(r) for r in rows if any(str(r.get(k)) in OUT_VALUES for k in keys)]
            out[table] = sorted(json.dumps({k: v for k, v in r.items() if not str(k).startswith(("last_", "updated_at"))}, default=str, sort_keys=True) for r in mine)
    return out


def scan_writes(email: str) -> list[str]:
    from test_cross_project_write_scan import SKIP_PREFIXES, _example, _resolve
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        _seed(db)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    findings: list[str] = []
    ids = {**IDS}
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            token = client.post("/api/v1/auth/login", json={"email": email, "password": "Clave12345!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            spec = app.openapi()
            import test_cross_project_write_scan as w
            original = dict(w.B_IDS)
            w.B_IDS.clear(); w.B_IDS.update(ids)  # el generador de cuerpos usa estos ids
            try:
                for path, operations in sorted(spec["paths"].items()):
                    if path.startswith(SKIP_PREFIXES):
                        continue
                    for method in ("post", "put", "patch", "delete"):
                        op = operations.get(method)
                        if not op:
                            continue
                        url = re.sub(r"{(\w+)}", lambda m: ids.get(m.group(1), "x"), path)
                        params = {p["name"]: ids.get(p["name"], "proj-t" if p["name"].endswith("_id") else "x")
                                  for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
                        kwargs: dict = {"params": params}
                        content = op.get("requestBody", {}).get("content", {})
                        if "application/json" in content:
                            body = _example(content["application/json"]["schema"], spec)
                            kwargs["json"] = json.loads(json.dumps(body).replace('"proj-b"', '"proj-t"'))
                        elif "multipart/form-data" in content or "application/x-www-form-urlencoded" in content:
                            schema = _resolve((content.get("multipart/form-data") or content["application/x-www-form-urlencoded"])["schema"], spec)
                            data, files = {}, {}
                            for key, prop in schema.get("properties", {}).items():
                                resolved = _resolve(prop, spec)
                                if resolved.get("format") == "binary" or resolved.get("contentMediaType"):
                                    files[key] = ("prueba.csv", b"a,b\n1,2\n", "text/csv")
                                else:
                                    value = _example(prop, spec, key)
                                    value = "proj-t" if value == "proj-b" else value
                                    data[key] = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                            kwargs.update(data=data, files=files or None)
                        before = _snapshot_out(engine)
                        response = client.request(method.upper(), url, headers=headers, **kwargs)
                        if _snapshot_out(engine) != before:
                            findings.append(f"{response.status_code} {method.upper()} {path}")
            finally:
                w.B_IDS.clear(); w.B_IDS.update(original)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
    return findings


def test_territorial_write_scan_detects_changes_for_unrestricted_admin():
    assert len(scan_writes("admin@example.com")) >= 5


def test_no_write_route_changes_participants_outside_the_users_territory():
    findings = scan_writes("coord@example.com")
    assert findings == [], "Rutas que modifican datos fuera del territorio:\n" + "\n".join(findings)
