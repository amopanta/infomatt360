"""Pruebas iniciales del backend.

Estas pruebas garantizan que la aplicacion arranca y que los endpoints de
salud responden correctamente. Son la base para integracion continua.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_v1_health() -> None:
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
