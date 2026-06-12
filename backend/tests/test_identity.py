from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_user_with_all_channels() -> None:
    payload = {
        "full_name": "Gestor de Campo",
        "document_id": "123456789",
        "email": "gestor@infomatt.test",
        "allowed_channels": ["web", "android", "desktop"]
    }
    response = client.post("/api/v1/identity/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["document_id"] == payload["document_id"]
    assert "android" in data["allowed_channels"]


def test_create_project() -> None:
    response = client.post("/api/v1/identity/projects", json={"name": "Proyecto Piloto"})
    assert response.status_code == 201
    assert response.json()["name"] == "Proyecto Piloto"


def test_create_role_with_permissions() -> None:
    payload = {
        "name": "Coordinador",
        "permissions": ["records.read", "records.approve", "reports.export"]
    }
    response = client.post("/api/v1/identity/roles", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "records.approve" in data["permissions"]
