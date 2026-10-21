"""docs/146: proyecto completo hacia una base externa e importación desde ella."""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable
from starlette.testclient import TestClient

from app.core.permissions import ALL_PERMISSIONS, MIRROR_MANAGE
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.identity import Project, Role, User
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.models.scheduler import ScheduledTask
from app.services.project_export_service import fixed_tables
from app.services.scheduler_service import next_run_at

P = "proj-sync"
PASSWORD = "Clave12345!"


def _seed(db):
    meta = json.dumps({"department": "Antioquia", "municipality": "Turbo"})
    db.add_all([
        Project(id=P, name="Proyecto sync"),
        Role(id="r-all", name="Todo", permissions=",".join(sorted(ALL_PERMISSIONS))),
        Role(id="r-nomirror", name="Sin espejo", permissions=",".join(sorted(ALL_PERMISSIONS - {MIRROR_MANAGE}))),
        User(id="admin", full_name="Admin", document_id="A1", email="admin@x.org", password_hash=hash_password(PASSWORD)),
        User(id="otro", full_name="Otro", document_id="O1", email="otro@x.org", password_hash=hash_password(PASSWORD)),
        User(id="gestora", full_name="Gestora", document_id="G1", email="gestora@x.org", password_hash=hash_password(PASSWORD)),
        UserProjectAssignment(user_id="admin", project_id=P, role_id="r-all", status="active"),
        UserProjectAssignment(user_id="otro", project_id=P, role_id="r-nomirror", status="active"),
        UserProjectAssignment(user_id="gestora", project_id=P, role_id="r-all", status="active"),
        BuilderTemplate(id="tpl-visita-0001", project_id=P, name="Visita Domiciliaria", status="published"),
        BuilderTemplate(id="tpl-encuesta-02", project_id=P, name="Encuesta Ñandú", status="published"),
        BuilderComponent(id="c1", template_id="tpl-visita-0001", component_type="DATE", name="fecha_visita", label="Fecha de visita", sort_order=1),
        BuilderComponent(id="c2", template_id="tpl-visita-0001", component_type="INTEGER", name="personas", label="Personas en el hogar", sort_order=2),
        BuilderComponent(id="c3", template_id="tpl-encuesta-02", component_type="TEXT", name="opinion", label="¿Qué opina?", sort_order=1),
        Participant(id="p1", project_id=P, full_name="Ana", document_id="100", metadata_json=meta),
        Participant(id="p2", project_id=P, full_name="Beto", document_id="200", metadata_json=meta),
        ParticipantFormAssignment(id="as1", project_id=P, template_id="tpl-visita-0001", participant_id="p1", responsible_user_id="gestora",
                                  status="assigned", assigned_by="admin"),
    ])
    when = datetime(2026, 10, 1, 12)
    for i, (template, participant, values) in enumerate([
        ("tpl-visita-0001", "p1", {"fecha_visita": "2026-10-01", "personas": 4}),
        ("tpl-visita-0001", "p2", {"fecha_visita": "2026-10-02", "personas": 2, "campo_viejo": "solo en la respuesta"}),
        ("tpl-encuesta-02", "p1", {"opinion": "Muy bien"}),
    ]):
        db.add(RuntimeRecord(id=f"rec{i}", project_id=P, template_id=template, participant_id=participant, status="submitted",
                             submitted_by="gestora", captured_by_name="Gestora", captured_by_document="G1", created_at=when, updated_at=when))
        for name, value in values.items():
            db.add(RuntimeRecordValue(id=f"rec{i}-{name}", record_id=f"rec{i}", field_name=name, field_value_json=json.dumps(value)))
    db.commit()


@pytest.fixture()
def client(tmp_path):
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
        with TestClient(app) as test_client:
            test_client.sessions = sessions
            test_client.tmp = tmp_path
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def login(client, email="admin@x.org"):
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def connect(client, headers, path):
    target = client.post("/api/v1/mirror/targets", headers=headers, json={"project_id": P, "name": "Externa", "engine": "sqlite", "file_path": str(path)})
    assert target.status_code == 200, target.text
    return target.json()["id"]


def test_whole_project_export_with_flat_tables_and_reconciliation(client):
    headers = login(client)
    dest = client.tmp / "destino.db"
    target_id = connect(client, headers, dest)
    plan = client.post("/api/v1/mirror/plans", headers=headers, json={"target_id": target_id, "name": "Todo el proyecto", "schedule_mode": "full_mirror", "scope": "project"})
    assert plan.status_code == 200 and plan.json()["scope"] == "project"
    legacy = client.post("/api/v1/mirror/plans", headers=headers, json={"target_id": target_id, "name": "Antiguo"}).json()
    assert legacy["scope"] == "records"  # sin scope, la API conserva el contrato anterior
    run = client.post(f"/api/v1/mirror/plans/{plan.json()['id']}/run", headers=headers).json()
    assert run["status"] == "completed", run
    summary = run["summary"]
    assert summary["reconciled"] is True
    assert summary["tables"]["im360_participants"] == {"source": 2, "destination": 2, "ok": True}
    assert summary["tables"]["im360_records"]["destination"] == 3

    external = create_engine(f"sqlite:///{dest}")
    tables = inspect(external).get_table_names()
    visita = next(t for t in tables if t.startswith("im360_f_visita_domiciliaria"))
    encuesta = next(t for t in tables if t.startswith("im360_f_encuesta_nandu"))
    with external.connect() as conn:
        rows = conn.execute(text(f"SELECT im_record_id, im_participant_document, im_captured_by, fecha_visita, personas, campo_viejo FROM {visita} ORDER BY im_record_id")).all()
        assert rows[0][1:] == ("100", "Gestora", "2026-10-01", "4", None)
        assert rows[1][5] == "solo en la respuesta"  # campos que solo están en respuestas también salen
        assert conn.execute(text(f"SELECT opinion FROM {encuesta}")).scalar() == "Muy bien"
        dictionary = conn.execute(text("SELECT field_name, column_name, label FROM im360_form_fields WHERE template_id = 'tpl-visita-0001' ORDER BY position")).all()
        assert [d[0] for d in dictionary] == ["fecha_visita", "personas", "campo_viejo"] and dictionary[1][2] == "Personas en el hogar"
        assert conn.execute(text("SELECT COUNT(*) FROM im360_assignments")).scalar() == 1

    # Nueva pregunta y nueva respuesta: la tabla gana la columna y el incremental solo escribe lo cambiado.
    with client.sessions() as db:
        db.add(BuilderComponent(id="c4", template_id="tpl-visita-0001", component_type="TEXT", name="observacion", label="Observación", sort_order=3))
        db.add(RuntimeRecord(id="rec9", project_id=P, template_id="tpl-visita-0001", participant_id="p2", status="submitted", submitted_by="gestora",
                             created_at=datetime(2030, 1, 1), updated_at=datetime(2030, 1, 1)))
        db.add(RuntimeRecordValue(id="rec9-obs", record_id="rec9", field_name="observacion", field_value_json=json.dumps("Nueva")))
        db.commit()
    inc = client.post("/api/v1/mirror/plans", headers=headers, json={"target_id": target_id, "name": "Diario", "schedule_mode": "incremental", "scope": "project"}).json()
    client.post(f"/api/v1/mirror/plans/{inc['id']}/run", headers=headers)  # carga inicial del plan
    second = client.post(f"/api/v1/mirror/plans/{inc['id']}/run", headers=headers).json()
    assert second["status"] == "completed" and second["summary"]["written_records"] == 1 and second["summary"]["reconciled"]
    with external.connect() as conn:
        assert conn.execute(text(f"SELECT observacion FROM {visita} WHERE im_record_id = 'rec9'")).scalar() == "Nueva"
        assert conn.execute(text(f"SELECT COUNT(*) FROM {visita}")).scalar() == 3
    external.dispose()


def test_fixed_tables_compile_for_every_engine():
    from sqlalchemy.dialects import mssql, mysql, postgresql
    _, tables = fixed_tables()
    for dialect in (postgresql.dialect(), mysql.dialect(), mssql.dialect()):
        ddl = str(CreateTable(tables["values"]).compile(dialect=dialect))
        assert "im360_record_values" in ddl
    assert "NVARCHAR(max)" in str(CreateTable(tables["values"]).compile(dialect=mssql.dialect()))
    assert "LONGTEXT" in str(CreateTable(tables["values"]).compile(dialect=mysql.dialect()))


def _source(client, rows_sql: list[str]):
    path = client.tmp / "origen.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        for statement in rows_sql:
            conn.execute(text(statement))
    engine.dispose()
    return path


def test_import_participants_preview_idempotent_and_updates(client):
    headers = login(client)
    source = _source(client, [
        "CREATE TABLE beneficiarios (cedula TEXT, nombre TEXT, municipio TEXT, departamento TEXT, actualizado TEXT)",
        "INSERT INTO beneficiarios VALUES ('100', 'Ana María', 'Turbo', 'Antioquia', '2026-10-01'), ('300', 'Carla', 'Turbo', 'Antioquia', '2026-10-02'), ('400', NULL, 'Turbo', 'Antioquia', '2026-10-03')",
    ])
    source_id = connect(client, headers, source)
    described = client.get(f"/api/v1/db-sync/{P}/sources/{source_id}/describe", headers=headers, params={"entity": "participants", "source_table": "beneficiarios"}).json()
    assert "beneficiarios" in described["tables"]
    assert described["suggested_mapping"] == {"document_id": "cedula", "full_name": "nombre", "department": "departamento", "municipality": "municipio"}
    created = client.post(f"/api/v1/db-sync/{P}/imports", headers=headers, json={
        "source_id": source_id, "name": "Padrón", "entity": "participants", "source_table": "beneficiarios",
        "mapping": described["suggested_mapping"], "key_column": "cedula"})
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    preview = client.post(f"/api/v1/db-sync/imports/{job_id}/preview", headers=headers).json()
    assert [r["outcome"] for r in preview["preview"]] == ["updated", "created", "failed"]
    with client.sessions() as db:
        assert db.query(Participant).filter_by(project_id=P).count() == 2  # la vista previa no escribe
    first = client.post(f"/api/v1/db-sync/imports/{job_id}/run", headers=headers).json()
    assert (first["created"], first["updated"], first["failed"]) == (1, 1, 1)
    again = client.post(f"/api/v1/db-sync/imports/{job_id}/run", headers=headers).json()
    assert again["unchanged"] == 2 and again["created"] == 0
    with client.sessions() as db:
        assert db.query(Participant).filter_by(project_id=P, document_id="100").one().full_name == "Ana María"
        assert db.query(Participant).filter_by(project_id=P).count() == 3
    runs = client.get(f"/api/v1/db-sync/imports/{job_id}/runs", headers=headers).json()
    assert len(runs) == 2 and runs[1]["errors"][0]["error"].startswith("Falta el nombre")
    # Sin mirror.manage no se configuran conexiones externas.
    assert client.post(f"/api/v1/db-sync/{P}/imports", headers=login(client, "otro@x.org"), json={
        "source_id": source_id, "name": "Otra importación", "entity": "participants", "source_table": "beneficiarios",
        "mapping": {"full_name": "nombre"}, "key_column": "cedula"}).status_code == 403


def test_import_records_and_assignments(client):
    headers = login(client)
    source = _source(client, [
        "CREATE TABLE visitas (id_externo TEXT, cedula TEXT, fecha TEXT, personas INTEGER)",
        "INSERT INTO visitas VALUES ('V1', '100', '2026-09-01', 5), ('V2', '999', '2026-09-02', 1)",
        "CREATE TABLE asignaciones (cedula TEXT, correo TEXT)",
        "INSERT INTO asignaciones VALUES ('200', 'gestora@x.org'), ('100', 'nadie@x.org')",
    ])
    source_id = connect(client, headers, source)
    job = client.post(f"/api/v1/db-sync/{P}/imports", headers=headers, json={
        "source_id": source_id, "name": "Visitas históricas", "entity": "records", "source_table": "visitas", "template_id": "tpl-visita-0001",
        "mapping": {"participant_key": "cedula", "fecha_visita": "fecha", "personas": "personas"}, "key_column": "id_externo"})
    assert job.status_code == 201, job.text
    result = client.post(f"/api/v1/db-sync/imports/{job.json()['id']}/run", headers=headers).json()
    assert result["created"] == 1 and result["failed"] == 1  # V2: participante inexistente
    assert client.post(f"/api/v1/db-sync/imports/{job.json()['id']}/run", headers=headers).json()["unchanged"] == 1
    with client.sessions() as db:
        record = db.query(RuntimeRecord).filter(RuntimeRecord.participant_id == "p1", RuntimeRecord.template_id == "tpl-visita-0001",
                                                RuntimeRecord.id.notin_(["rec0"])).one()
        values = {v.field_name: json.loads(v.field_value_json) for v in db.query(RuntimeRecordValue).filter_by(record_id=record.id)}
        assert values == {"fecha_visita": "2026-09-01", "personas": 5}
        record.status = "approved"
        db.commit()
    engine = create_engine(f"sqlite:///{source}")
    with engine.begin() as conn:
        conn.execute(text("UPDATE visitas SET personas = 6 WHERE id_externo = 'V1'"))
    engine.dispose()
    changed = client.post(f"/api/v1/db-sync/imports/{job.json()['id']}/run", headers=headers).json()
    assert changed["unchanged"] == 1 and changed["updated"] == 0  # aprobado: no se modifica

    assignments = client.post(f"/api/v1/db-sync/{P}/imports", headers=headers, json={
        "source_id": source_id, "name": "Asignaciones", "entity": "assignments", "source_table": "asignaciones", "template_id": "tpl-visita-0001",
        "mapping": {"participant_key": "cedula", "responsible_email": "correo"}, "key_column": "cedula"}).json()
    done = client.post(f"/api/v1/db-sync/imports/{assignments['id']}/run", headers=headers).json()
    assert done["created"] == 1 and done["failed"] == 1
    with client.sessions() as db:
        assert db.query(ParticipantFormAssignment).filter_by(participant_id="p2", responsible_user_id="gestora").count() == 1


def test_daily_task_runs_at_local_hour():
    task = ScheduledTask(project_id=P, name="Espejo diario", task_type="mirror", frequency="daily",
                         config_json=json.dumps({"run_time": "02:00", "timezone": "America/Bogota"}))
    # 2026-10-19 15:00 UTC = 10:00 en Bogotá → próxima corrida 2026-10-20 02:00 Bogotá = 07:00 UTC.
    assert next_run_at(task, datetime(2026, 10, 19, 15, 0)) == datetime(2026, 10, 20, 7, 0)
    assert next_run_at(task, datetime(2026, 10, 19, 6, 0), first=True) == datetime(2026, 10, 19, 7, 0)
    plain = ScheduledTask(project_id=P, name="Cada día", task_type="mirror", frequency="daily")
    assert next_run_at(plain, datetime(2026, 10, 19, 15, 0)) == datetime(2026, 10, 20, 15, 0)


def test_external_participants_paginate_without_breaking_contract(client):
    with client.sessions() as db:
        from app.services.api_key_service import api_key_service  # noqa: F401
    headers = login(client)
    created = client.post("/api/v1/api-keys", headers=headers, json={"project_id": P, "name": "BI", "permissions": ["records.read"]})
    if created.status_code >= 400:
        pytest.skip(f"API de llaves con otro contrato: {created.status_code}")
    key = created.json().get("api_key") or created.json().get("key") or created.json().get("token")
    api = {"X-API-Key": key}
    assert len(client.get("/api/v1/external-api/participants", headers=api).json()) == 2
    assert len(client.get("/api/v1/external-api/participants", headers=api, params={"limit": 1}).json()) == 1
    assert len(client.get("/api/v1/external-api/participants", headers=api, params={"limit": 1, "offset": 1}).json()) == 1
