"""H06: sincronización idempotente y fallos parciales en lotes de la app de campo."""

import json

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.builder import BuilderTemplate
from app.models.identity import Role
from app.models.runtime_record import RuntimeRecord
from test_xlsform_nested_and_system_fields import _build_xlsform, _import, auth, setup_client


def _published_form(client, headers, sessions):
    content = _build_xlsform(survey_rows=[["text", "nombre", "Nombre"]], choices_rows=[])
    template_id = _import(client, headers, content)["template_id"]
    with sessions() as db:
        db.get(BuilderTemplate, template_id).status = "published"
        db.commit()
    return template_id


def _record(template_id, name, participant_id=None):
    return {"project_id": "xlsform-project", "template_id": template_id, "status": "submitted", "participant_id": participant_id,
            "values": [{"field_name": "nombre", "field_value_json": json.dumps(name)}]}


def test_same_batch_sent_three_times_creates_each_record_once_and_partial_errors_do_not_block():
    engine, sessions = setup_client()
    with sessions() as db:
        db.get(Role, "xlsform-builder-role").permissions = "builder.write,records.write,records.read"
        db.commit()
    try:
        with TestClient(app) as client:
            headers = auth(client, "xlsform-builder@example.com", "Builder12345!")
            template_id = _published_form(client, headers, sessions)
            batch = {"project_id": "xlsform-project", "template_id": template_id, "idempotency_key": "h06" + "a" * 61,
                     "records": [_record(template_id, "Ana"), _record(template_id, "Mal", participant_id="no-existe"), _record(template_id, "Luis")]}
            responses = [client.post("/api/v1/runtime/session/bulk-save", headers=headers, json=batch) for _ in range(3)]
            assert [r.status_code for r in responses] == [200, 200, 200], [r.text for r in responses]
            first = responses[0].json()["results"]
            statuses = [item["status"] for item in first]
            # El registro inválido se informa solo, sin bloquear a los demás
            assert statuses[0] == statuses[2] == "created" and statuses[1] == "failed", first
            assert first[1]["error"]
            # Reenvíos: misma respuesta, sin crear nada nuevo
            for again in responses[1:]:
                assert again.json()["replayed"] is True
                assert [i["id"] for i in again.json()["results"]] == [i["id"] for i in first]
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == template_id).count() == 2

            # La app reintenta solo el que falló, ya corregido, con otra clave: se crea una vez
            fixed = {"project_id": "xlsform-project", "template_id": template_id, "idempotency_key": "h06" + "b" * 61,
                     "records": [_record(template_id, "Mal corregido")]}
            for _ in range(3):
                assert client.post("/api/v1/runtime/session/bulk-save", headers=headers, json=fixed).status_code == 200
            with sessions() as db:
                assert db.query(RuntimeRecord).filter(RuntimeRecord.template_id == template_id).count() == 3
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
