"""Monitoreo de equipos de campo: latido, tablero del supervisor y recorrido."""

from datetime import timedelta

from starlette.testclient import TestClient

from app.api.v1.field_devices import haversine_km
from app.core.time import utc_now
from app.db.base import Base
from app.main import app
from app.models.audit import AuditLog
from app.models.device_status import FieldDeviceStatus, FieldRoutePoint
from test_form_assignments_reopening import auth, setup_client

PROJECT = "assign-project"


def _iso(value):
    return value.isoformat() + "Z"


def test_heartbeat_feeds_supervisor_board_and_route():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            gestor = auth(client, "assign-owner@example.com", "Owner12345!")
            now = utc_now()
            points = [
                {"latitude": 4.6097, "longitude": -74.0817, "accuracy_m": 8, "recorded_at": _iso(now - timedelta(minutes=10))},
                {"latitude": 4.6187, "longitude": -74.0817, "accuracy_m": 9, "recorded_at": _iso(now - timedelta(minutes=5))},
                # Punto con mala precisión: se guarda pero no suma distancia
                {"latitude": 4.7000, "longitude": -74.0817, "accuracy_m": 450, "recorded_at": _iso(now - timedelta(minutes=2))},
            ]
            beat = {
                "device_id": "tablet-0001", "project_id": PROJECT, "device_name": "Tablet Soacha 1",
                "platform": "android 14", "app_version": "1.2.0",
                "pending_count": 3, "error_count": 1, "pending_evidence_count": 2,
                "oldest_pending_at": _iso(now - timedelta(hours=2)), "last_sync_at": _iso(now - timedelta(hours=3)),
                "recent_errors": [{"at": _iso(now - timedelta(minutes=30)), "message": "Campo obligatorio: edad"}],
                "route_points": points,
            }
            sent = client.post("/api/v1/field-devices/heartbeat", headers=gestor, json=beat)
            assert sent.status_code == 200, sent.text
            assert sent.json()["received_points"] == 3
            # Reenvío por respuesta perdida: no duplica puntos
            again = client.post("/api/v1/field-devices/heartbeat", headers=gestor, json=beat)
            assert again.status_code == 200 and again.json()["received_points"] == 0

            # El gestor no ve el tablero ni el recorrido (solo supervisión)
            assert client.get(f"/api/v1/field-devices/project/{PROJECT}/status", headers=gestor).status_code == 403
            period = {"date_from": _iso(now - timedelta(days=1)), "date_to": _iso(now + timedelta(hours=1))}
            assert client.get(f"/api/v1/field-devices/project/{PROJECT}/routes", headers=gestor, params=period).status_code == 403

            board = client.get(f"/api/v1/field-devices/project/{PROJECT}/status", headers=admin)
            assert board.status_code == 200, board.text
            [device] = board.json()
            assert device["user_name"] == "Responsable" and device["device_name"] == "Tablet Soacha 1"
            assert device["pending_count"] == 3 and device["level"] == "danger"
            assert "1 registro(s) con error" in device["alerts"] and "3 registro(s) sin enviar" in device["alerts"]
            assert device["last_error"] == "Campo obligatorio: edad"
            assert device["last_latitude"] == 4.7

            team = client.get(f"/api/v1/field-devices/project/{PROJECT}/routes", headers=admin, params=period)
            assert team.status_code == 200, team.text
            [summary] = team.json()
            assert summary["point_count"] == 3 and summary["points"] == []
            expected = round(haversine_km((4.6097, -74.0817), (4.6187, -74.0817)), 2)
            assert summary["distance_km"] == expected and 0.9 < expected < 1.1

            detail = client.get(f"/api/v1/field-devices/project/{PROJECT}/routes", headers=admin,
                                params={**period, "user_id": "assign-owner"})
            assert [p["latitude"] for p in detail.json()[0]["points"]] == [4.6097, 4.6187, 4.7]

            # Todo enviado: el equipo queda en verde
            ok = client.post("/api/v1/field-devices/heartbeat", headers=gestor, json={
                "device_id": "tablet-0001", "project_id": PROJECT, "last_sync_at": _iso(utc_now())})
            assert ok.status_code == 200
            device = client.get(f"/api/v1/field-devices/project/{PROJECT}/status", headers=admin).json()[0]
            assert device["level"] == "ok" and device["alerts"] == [] and device["last_error"] is None
            with sessions() as db:
                assert db.query(FieldDeviceStatus).count() == 1
                assert db.query(FieldRoutePoint).count() == 3
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_stale_device_with_pending_data_is_flagged_and_project_access_is_checked():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            gestor = auth(client, "assign-owner@example.com", "Owner12345!")
            denied = client.post("/api/v1/field-devices/heartbeat", headers=gestor,
                                 json={"device_id": "tablet-0002", "project_id": "otro-proyecto"})
            assert denied.status_code == 403
            assert client.post("/api/v1/field-devices/heartbeat", headers=gestor, json={
                "device_id": "tablet-0002", "project_id": PROJECT, "pending_count": 5,
                "oldest_pending_at": _iso(utc_now() - timedelta(days=3))}).status_code == 200
            with sessions() as db:
                row = db.query(FieldDeviceStatus).one()
                row.last_seen_at = utc_now() - timedelta(days=2)
                db.commit()
            device = client.get(f"/api/v1/field-devices/project/{PROJECT}/status", headers=admin).json()[0]
            assert device["level"] == "danger"
            assert "5 registro(s) sin enviar hace más de un día" in device["alerts"]
            assert "Sin conexión con el servidor hace más de un día" in device["alerts"]
            too_long = client.get(f"/api/v1/field-devices/project/{PROJECT}/routes", headers=admin, params={
                "date_from": _iso(utc_now() - timedelta(days=40)), "date_to": _iso(utc_now())})
            assert too_long.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_remote_wipe_is_admin_only_reaches_device_and_is_confirmed():
    """H07: tablet perdida o reasignada."""
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            gestor = auth(client, "assign-owner@example.com", "Owner12345!")
            beat = {"device_id": "tablet-0003", "project_id": PROJECT, "pending_count": 2}
            assert client.post("/api/v1/field-devices/heartbeat", headers=gestor, json=beat).json()["wipe_requested"] is False
            order = {"device_id": "tablet-0003", "user_id": "assign-owner"}
            # El propio gestor (sin gestión de usuarios) no puede pedirlo
            assert client.post(f"/api/v1/field-devices/project/{PROJECT}/wipe", headers=gestor, json=order).status_code == 403
            requested = client.post(f"/api/v1/field-devices/project/{PROJECT}/wipe", headers=admin, json=order)
            assert requested.status_code == 200, requested.text
            assert requested.json()["wipe_requested_at"] and requested.json()["wipe_completed_at"] is None
            assert client.post(f"/api/v1/field-devices/project/{PROJECT}/wipe", headers=admin,
                               json={**order, "device_id": "no-existe"}).status_code == 404

            assert client.post("/api/v1/field-devices/heartbeat", headers=gestor, json=beat).json()["wipe_requested"] is True
            assert client.post("/api/v1/field-devices/wipe-ack", headers=gestor, json={"device_id": "tablet-0003"}).json() == {"wiped": True}
            device = client.get(f"/api/v1/field-devices/project/{PROJECT}/status", headers=admin).json()[0]
            assert device["wipe_completed_at"] and device["pending_count"] == 0
            # Ya confirmado: el siguiente latido no vuelve a pedir el borrado
            assert client.post("/api/v1/field-devices/heartbeat", headers=gestor, json={**beat, "pending_count": 0}).json()["wipe_requested"] is False
            with sessions() as db:
                actions = [row.action for row in db.query(AuditLog).filter(AuditLog.module == "field_devices").all()]
            assert actions == ["remote_wipe_requested", "remote_wipe_completed"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_route_days_and_visits_with_participant_and_gps():
    """Trazabilidad de visitas (docs/150): el supervisor ve qué días hay
    recorrido y, por día, a quién visitó cada gestor y dónde."""
    from app.models.builder import BuilderComponent
    from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            admin = auth(client, "assign-admin@example.com", "Admin12345!")
            gestor = auth(client, "assign-owner@example.com", "Owner12345!")
            now = utc_now()
            client.post("/api/v1/field-devices/heartbeat", headers=gestor, json={
                "device_id": "tablet-0002", "project_id": PROJECT,
                "route_points": [{"latitude": 4.61, "longitude": -74.08, "accuracy_m": 5, "recorded_at": _iso(now - timedelta(minutes=20))}]})
            with sessions() as db:
                db.add(BuilderComponent(template_id="closed-form", component_type="GPS", name="ubicacion", label="Ubicación", sort_order=1))
                db.add_all([
                    RuntimeRecord(id="visit-1", project_id=PROJECT, template_id="closed-form", participant_id="assign-p1",
                                  submitted_by="assign-owner", status="submitted", created_at=now - timedelta(minutes=15)),
                    RuntimeRecord(id="visit-2", project_id=PROJECT, template_id="closed-form", participant_id="assign-p2",
                                  submitted_by="assign-owner", status="submitted", created_at=now - timedelta(minutes=5)),
                ])
                db.add(RuntimeRecordValue(record_id="visit-1", field_name="ubicacion", field_value_json='{"lat": 4.6123, "lng": -74.0811}'))
                db.commit()

            days = client.get(f"/api/v1/field-devices/project/{PROJECT}/route-days", headers=admin, params={"tz_offset_minutes": 0})
            assert days.status_code == 200, days.text
            assert days.json()[0] == {"day": (now - timedelta(minutes=20)).date().isoformat(), "user_count": 1, "point_count": 1, "visit_count": 2}
            assert client.get(f"/api/v1/field-devices/project/{PROJECT}/route-days", headers=gestor).status_code == 403

            period = {"date_from": _iso(now - timedelta(hours=1)), "date_to": _iso(now + timedelta(minutes=1)), "user_id": "assign-owner"}
            visits = client.get(f"/api/v1/field-devices/project/{PROJECT}/visits", headers=admin, params=period)
            assert visits.status_code == 200, visits.text
            first, second = visits.json()
            assert first["participant_name"] == "Primera" and first["participant_document"] == "1001"
            assert (first["latitude"], first["longitude"]) == (4.6123, -74.0811)
            # Sin campo GPS diligenciado: se lista la visita, sin punto en el mapa
            assert second["participant_name"] == "Segunda" and second["latitude"] is None
            assert client.get(f"/api/v1/field-devices/project/{PROJECT}/visits", headers=gestor, params=period).status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
