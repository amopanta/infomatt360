"""Repeat anidado y escalas sin lista en el importador; campos de sistema al guardar."""

import json

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Role
from test_xlsform_import import _build_xlsform, auth, setup_client

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _import(client: TestClient, headers: dict[str, str], content: bytes) -> dict:
    response = client.post("/api/v1/xlsform/import", headers=headers, data={"project_id": "xlsform-project"}, files={"upload": ("prueba.xlsx", content, XLSX)})
    assert response.status_code == 200, response.text
    return response.json()


def test_nested_repeat_stays_inside_parent_and_scales_get_options():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "xlsform-builder@example.com", "Builder12345!")
            content = _build_xlsform(
                survey_rows=[
                    ["LIKERT_5", "satisfaccion", "Satisfacción"],
                    ["NPS", "recomendacion", "Recomendación"],
                    ["RATING", "estrellas", "Estrellas"],
                    ["DROPDOWN", "sin_lista", "Lista sin opciones"],
                    ["begin_repeat", "integrantes", "Integrantes"],
                    ["text", "nombre", "Nombre"],
                    ["begin_repeat", "contactos", "Contactos"],
                    ["text", "telefono", "Teléfono"],
                    ["end_repeat", "", ""],
                    ["end_repeat", "", ""],
                ],
                choices_rows=[["likert5", "1", "Muy en desacuerdo"], ["likert5", "5", "Muy de acuerdo"]],
            )
            body = _import(client, headers, content)
            assert any("sin_lista" in warning and "sin lista de opciones" in warning for warning in body["warnings"])

            with sessions() as db:
                components = {c.name: c for c in db.query(BuilderComponent).filter(BuilderComponent.template_id == body["template_id"]).all()}
            assert "contactos" not in components, "el repeat anidado no debe aplanarse"
            integrantes = json.loads(components["integrantes"].config_json)
            nested = next(field for field in integrantes["fields"] if field["name"] == "contactos")
            assert nested["component_type"] == "REPEAT"
            assert [field["name"] for field in nested["config"]["fields"]] == ["telefono"]

            assert [o["label"] for o in json.loads(components["satisfaccion"].config_json)["options"]] == ["Muy en desacuerdo", "Muy de acuerdo"]
            assert [o["value"] for o in json.loads(components["recomendacion"].config_json)["options"]] == [str(n) for n in range(11)]
            assert len(json.loads(components["estrellas"].config_json)["options"]) == 5
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_system_fields_are_filled_by_server_and_captured_by_cannot_be_spoofed():
    engine, sessions = setup_client()
    with sessions() as db:
        db.get(Role, "xlsform-builder-role").permissions = "builder.write,records.write,records.read"
        db.commit()
    try:
        with TestClient(app) as client:
            headers = auth(client, "xlsform-builder@example.com", "Builder12345!")
            content = _build_xlsform(
                survey_rows=[
                    ["text", "nombre", "Nombre"],
                    ["CAPTURED_BY", "capturador", "Quién lo llenó"],
                    ["RESPONSE_ID", "id_respuesta", "Número de respuesta"],
                    ["UUID", "uid", "Identificador"],
                    ["CHANGE_HISTORY", "historial", "Historial"],
                ],
                choices_rows=[],
            )
            template_id = _import(client, headers, content)["template_id"]
            with sessions() as db:
                db.get(BuilderTemplate, template_id).status = "published"
                db.commit()

            saved = client.post("/api/v1/runtime/save", headers=headers, json={
                "project_id": "xlsform-project", "template_id": template_id,
                "values": [
                    {"field_name": "nombre", "field_value_json": json.dumps("Ana")},
                    {"field_name": "capturador", "field_value_json": json.dumps("Otra persona")},
                ],
            })
            assert saved.status_code == 200, saved.text
            record = saved.json()
            values = {v["field_name"]: json.loads(v["field_value_json"]) for v in record["values"]}
            assert values["capturador"] == "Builder"  # full_name del usuario autenticado
            assert values["id_respuesta"] == record["id"]
            assert len(values["uid"]) == 36
            assert values["historial"][0]["accion"] == "creado"
            assert values["historial"][0]["usuario"] == "Builder"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
