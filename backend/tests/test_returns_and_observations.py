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


def test_clean_export_defaults_to_approved_and_filters_period_quality_export_is_separate():
    engine, sessions = setup_client()
    _legacy_form(sessions)
    try:
        with TestClient(app) as client:
            coord = auth(client, "assign-admin@example.com", "Admin12345!")
            juan = auth(client, "assign-owner@example.com", "Owner12345!")
            ids = [client.post("/api/v1/runtime/save", headers=juan, json={
                "project_id": PROJECT, "template_id": "visita-3",
                "values": [{"field_name": "nombre", "field_value_json": json.dumps(f"Hogar {i}")}]}).json()["id"] for i in range(3)]
            for record_id in ids[:2]:
                client.post("/api/v1/review/actions", headers=coord, json={"project_id": PROJECT, "record_id": record_id, "to_status": "approved", "action": "approve"})
            client.post(f"/api/v1/review/records/{ids[2]}/return", headers=coord, json={
                "notes": "Revisar", "observations": [{"field_name": "nombre", "reason": "Nombre incompleto"}, {"field_name": "nombre", "reason": "Falta apellido"}]})

            clean = client.get("/api/v1/runtime/template/visita-3/records/clean-export.csv", headers=coord).content.decode("utf-8-sig")
            assert ids[0] in clean and ids[1] in clean and ids[2] not in clean  # solo aprobados
            assert "Nombre incompleto" not in clean
            everything = client.get("/api/v1/runtime/template/visita-3/records/clean-export.csv", headers=coord, params={"status": "todos"}).content.decode("utf-8-sig")
            assert all(i in everything for i in ids) and everything.count(ids[2]) == 1  # dos observaciones, una sola fila
            future = client.get("/api/v1/runtime/template/visita-3/records/clean-export.csv", headers=coord,
                                params={"status": "todos", "date_from": "2099-01-01T00:00:00Z"}).content.decode("utf-8-sig")
            assert not any(i in future for i in ids)

            quality = client.get("/api/v1/runtime/template/visita-3/records/observations.csv", headers=coord).content.decode("utf-8-sig")
            lines = [line for line in quality.splitlines() if ids[2] in line]
            assert len(lines) == 2 and all(line.startswith("observacion,") for line in lines)
            assert "Nombre incompleto" in quality and "Hogar 0" not in quality  # sin respuestas
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_bulk_return_1000_rows_with_partial_errors_retries_without_duplicates():
    """docs/141 §11: devolución masiva de 1.000 filas con errores parciales."""
    import csv
    import io
    from app.models.runtime_record import RuntimeRecord as RR
    engine, sessions = setup_client()
    _legacy_form(sessions)
    with sessions() as db:
        for i in range(500):
            db.add(RR(id=f"bulk-{i}", project_id=PROJECT, template_id="visita-3", status="submitted", submitted_by="assign-owner"))
        db.add(RR(id="bulk-aprobado", project_id=PROJECT, template_id="visita-3", status="approved", submitted_by="assign-owner"))
        db.commit()
    try:
        with TestClient(app) as client:
            coord = auth(client, "assign-admin@example.com", "Admin12345!")
            juan = auth(client, "assign-owner@example.com", "Owner12345!")
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id_registro", "accion", "usuario_destino", "observacion", "campo", "motivo"])
            for i in range(490):  # 490 registros x 2 observaciones = 980 filas válidas
                action, dest = ("reasignar", "assign-other@example.com") if i % 2 else ("devolver_original", "")
                w.writerow([f"bulk-{i}", action, dest, "Revisar", "fecha_visita", "Fecha inválida"])
                w.writerow([f"bulk-{i}", action, dest, "Revisar", "integrantes[0].firma", "Falta firma"])
            w.writerow(["no-existe", "devolver_original", "", "x", "c", "motivo"])           # error: registro
            w.writerow(["bulk-490", "borrar", "", "x", "c", "motivo"])                        # error: acción
            w.writerow(["bulk-491", "reasignar", "nadie@example.com", "x", "c", "motivo"])    # error: destinatario
            w.writerow(["bulk-aprobado", "devolver_original", "", "x", "c", "motivo"])        # error: estado
            w.writerow(["bulk-0", "devolver_original", "", "Revisar", "fecha_visita", "Fecha inválida"])  # duplicada
            for i in range(492, 497):
                w.writerow([f"bulk-{i}", "devolver_original", "", "", "c", ""])                # error: sin motivo
            w.writerow(["bulk-497", "reasignar", "assign-other@example.com", "x", "a", "m1"])
            w.writerow(["bulk-497", "devolver_original", "", "x", "b", "m2"])                 # error: acción distinta
            for i in range(8):
                w.writerow([f"bulk-49{8 + i % 2}", "devolver_original", "", "Revisar", f"campo_{i}", f"motivo {i}"])
            content = buf.getvalue().encode("utf-8")
            assert content.count(b"\n") - 1 == 1000
            upload = lambda preview: client.post(f"/api/v1/review/bulk-returns/{PROJECT}", headers=coord,
                                                 data={"preview_only": str(preview).lower()}, files={"upload": ("devoluciones.csv", content, "text/csv")})
            assert client.post(f"/api/v1/review/bulk-returns/{PROJECT}", headers=juan, data={"preview_only": "true"},
                               files={"upload": ("d.csv", content, "text/csv")}).status_code == 403
            preview = upload(True).json()
            assert preview["filas"] == 1000 and preview["errores"] == 10 and preview["duplicadas"] == 1
            assert preview["registros_a_devolver"] == 493  # 490 + bulk-497 + bulk-498 + bulk-499
            with sessions() as db:
                assert db.query(RR).filter(RR.status == "returned").count() == 0  # la vista previa no cambia nada
            applied = upload(False).json()
            assert applied["aplicadas"] == 493 and applied["errores"] == 10
            assert "bulk-aprobado" in applied["errores_csv"] and "no-existe" in applied["errores_csv"]
            with sessions() as db:
                assert db.query(RR).filter(RR.status == "returned").count() == 493
                assert db.query(ReviewObservation).count() == 980 + 1 + 8
                assert db.get(RR, "bulk-1").correction_user_id == "assign-other" and db.get(RR, "bulk-1").submitted_by == "assign-owner"
                assert db.get(RR, "bulk-0").correction_user_id is None
            again = upload(False).json()  # reintento con el mismo archivo
            assert again["aplicadas"] == 0 and again["ya_aplicadas"] == 980 + 1 + 8
            with sessions() as db:
                assert db.query(ReviewObservation).count() == 980 + 1 + 8
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
