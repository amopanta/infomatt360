"""docs/141 §10: ejemplo operativo integral de devolución con reasignación."""

import json

from starlette.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.models.builder import BuilderTemplate
from app.models.review import ReviewObservation
from app.models.runtime_record import RuntimeRecord
from test_form_assignments_reopening import auth, setup_client

PROJECT = "assign-project"


def _legacy_form(sessions):
    with sessions() as db:
        db.add(BuilderTemplate(id="visita-3", project_id=PROJECT, name="Visita 3", status="published"))
        db.commit()


def test_return_reassign_correct_offline_package_verify_and_clean_exports():
    engine, sessions = setup_client()
    _legacy_form(sessions)
    try:
        with TestClient(app) as client:
            coord = auth(client, "assign-admin@example.com", "Admin12345!")   # revisor
            juan = auth(client, "assign-owner@example.com", "Owner12345!")    # autor
            maria = auth(client, "assign-other@example.com", "Other12345!")   # corrige
            saved = client.post("/api/v1/runtime/save", headers=juan, json={
                "project_id": PROJECT, "template_id": "visita-3", "values": [
                    {"field_name": "fecha_visita", "field_value_json": json.dumps("2026-13-01")},
                    {"field_name": "integrantes", "field_value_json": json.dumps([
                        {"id": "integrantes_1", "index": 0, "values": {"nombre": "Ana", "firma": None}}])},
                ]})
            assert saved.status_code == 200, saved.text
            record_id = saved.json()["id"]
            fix = lambda field, value, version: {"field_name": field, "field_value_json": json.dumps(value), "expected_lock_version": version}

            # 1. Enviado = bloqueado, también para el autor
            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=juan, json=fix("fecha_visita", "2026-01-13", 1)).status_code == 400

            # 2. Dos observaciones y reasignación a María (el gestor no puede devolver)
            body = {"notes": "Fecha y firma incorrectas", "assignee_user_id": "assign-other", "observations": [
                {"field_name": "fecha_visita", "reason": "La fecha no existe", "requested_action": "Corregir fecha", "client_ref": "fila-1"},
                {"field_name": "firma", "repeat_path": "integrantes[0].firma", "reason": "Falta la firma de Ana", "client_ref": "fila-2"},
            ]}
            assert client.post(f"/api/v1/review/records/{record_id}/return", headers=juan, json=body).status_code == 403
            returned = client.post(f"/api/v1/review/records/{record_id}/return", headers=coord, json=body)
            assert returned.status_code == 200, returned.text
            assert returned.json()["correction_user_id"] == "assign-other"
            assert [o["status"] for o in returned.json()["observations"]] == ["pending", "pending"]

            # 3. Solo María corrige y reenvía; el autor original no cambia
            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=juan, json=fix("fecha_visita", "2026-01-13", 1)).status_code == 403
            mine = client.get(f"/api/v1/review/my-corrections/{PROJECT}", headers=maria).json()
            assert [r["record_id"] for r in mine] == [record_id] and mine[0]["pending_observations"] == 2
            assert client.get(f"/api/v1/review/my-corrections/{PROJECT}", headers=juan).json() == []
            package = client.get(f"/api/v1/review/records/{record_id}/correction-package", headers=maria)
            assert package.status_code == 200, package.text
            assert {v["field_name"] for v in package.json()["values"]} >= {"fecha_visita", "integrantes"}
            assert package.json()["author_id"] == "assign-owner" and package.json()["lock_version"] == 1
            assert [o["repeat_path"] for o in package.json()["observations"]] == [None, "integrantes[0].firma"]
            assert client.get(f"/api/v1/review/records/{record_id}/correction-package", headers=juan).status_code == 404

            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=maria, json=fix("fecha_visita", "2026-01-13", 1)).status_code == 200
            firma = client.post("/api/v1/files/upload", headers=maria, data={"project_id": PROJECT, "asset_type": "SIGNATURE", "record_id": record_id},
                                files={"upload": ("firma.png", b"PNG-firma", "image/png")})
            assert firma.status_code == 201, firma.text
            integrantes = [{"id": "integrantes_1", "index": 0, "values": {"nombre": "Ana", "firma": {"file_asset_id": firma.json()["id"], "name": "firma.png"}}}]
            assert client.patch(f"/api/v1/runtime/record/{record_id}/correction", headers=maria, json=fix("integrantes", integrantes, 2)).status_code == 200
            for obs in package.json()["observations"]:
                assert client.patch(f"/api/v1/review/observations/{obs['id']}", headers=juan, json={"status": "corrected"}).status_code == 403
                assert client.patch(f"/api/v1/review/observations/{obs['id']}", headers=maria, json={"status": "corrected", "note": "Listo"}).status_code == 200
            for state in ("corrected", "submitted"):
                assert client.post("/api/v1/review/actions", headers=juan, json={"project_id": PROJECT, "record_id": record_id, "to_status": state, "action": state}).status_code == 403
                response = client.post("/api/v1/review/actions", headers=maria, json={"project_id": PROJECT, "record_id": record_id, "to_status": state, "action": state})
                assert response.status_code == 200, response.text

            # 4. El coordinador verifica (el gestor no puede verificar) y aprueba
            for obs in package.json()["observations"]:
                assert client.patch(f"/api/v1/review/observations/{obs['id']}", headers=maria, json={"status": "verified"}).status_code == 403
                assert client.patch(f"/api/v1/review/observations/{obs['id']}", headers=coord, json={"status": "verified"}).status_code == 200
            approved = client.post("/api/v1/review/actions", headers=coord, json={"project_id": PROJECT, "record_id": record_id, "to_status": "approved", "action": "approve"})
            assert approved.status_code == 200, approved.text
            with sessions() as db:
                record = db.get(RuntimeRecord, record_id)
                assert record.submitted_by == "assign-owner" and record.status == "approved"
                assert {o.status for o in db.query(ReviewObservation).filter_by(record_id=record_id)} == {"verified"}

            # 5. Respuestas limpias sin observaciones ni filas repetidas; calidad aparte
            answers = client.get(f"/api/v1/runtime/template/visita-3/records/export.csv", headers=coord)
            assert answers.status_code == 200
            text = answers.content.decode("utf-8-sig")
            assert "Falta la firma" not in text and "La fecha no existe" not in text
            assert text.count(record_id) == 1
            assert "2026-01-13" in text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_return_rejects_assignee_without_capture_permission_and_retries_do_not_duplicate():
    engine, sessions = setup_client()
    _legacy_form(sessions)
    try:
        with TestClient(app) as client:
            coord = auth(client, "assign-admin@example.com", "Admin12345!")
            juan = auth(client, "assign-owner@example.com", "Owner12345!")
            record_id = client.post("/api/v1/runtime/save", headers=juan, json={
                "project_id": PROJECT, "template_id": "visita-3",
                "values": [{"field_name": "fecha_visita", "field_value_json": json.dumps("x")}]}).json()["id"]
            bad = client.post(f"/api/v1/review/records/{record_id}/return", headers=coord,
                              json={"notes": "Revisar", "assignee_user_id": "no-existe"})
            assert bad.status_code == 400
            with sessions() as db:
                assert db.get(RuntimeRecord, record_id).status == "submitted"  # nada cambió
            body = {"notes": "Revisar fecha", "observations": [{"field_name": "fecha_visita", "reason": "Fecha inválida", "client_ref": "lote-7-fila-3"}]}
            assert client.post(f"/api/v1/review/records/{record_id}/return", headers=coord, json=body).status_code == 200
            with sessions() as db:
                assert db.get(RuntimeRecord, record_id).correction_user_id is None  # vuelve al autor
                assert db.query(ReviewObservation).filter_by(record_id=record_id).count() == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
