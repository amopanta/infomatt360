"""Pantalla de Marca (docs/122): subida del logo, servido publico y enlace
proyecto-organizacion.

El bloque de logo del constructor de actas (docs/109) siempre dependio del
branding de la organizacion, pero no existia ninguna forma de cargar ese
logo desde la interfaz ni de vincular un proyecto existente a una
organizacion -- estas pruebas cubren ambas piezas nuevas.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User
from app.models.organization import OrganizationBranding
from app.services import organization_service as organization_service_module

# PNG valido de 1x1 pixel (firma + IHDR + IDAT + IEND).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6260f8cfc000000301010018dd8db00000000049454e44ae426082"
)


@pytest.fixture()
def branding_client(monkeypatch):
    # tempfile.mkdtemp() en vez del fixture tmp_path de pytest: en esta
    # maquina Windows el directorio base 'pytest-of-Pedro' esta bloqueado
    # (mismo problema conocido que afecta a test_file_upload/test_health).
    tmp_path = Path(tempfile.mkdtemp(prefix="branding-logo-test-"))
    monkeypatch.setattr(settings, "upload_directory", str(tmp_path))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="logo-project", name="Proyecto Logo")
        admin_role = Role(id="logo-admin-role", name="Admin Logo", permissions="organizations.manage,organizations.branding.manage")
        basic_role = Role(id="logo-basic-role", name="Basico Logo", permissions="records.read")
        admin = User(id="logo-admin", full_name="Admin", document_id="logo-admin-doc", email="logo-admin@example.com", password_hash=hash_password("Admin12345!"))
        basic = User(id="logo-basic", full_name="Basic", document_id="logo-basic-doc", email="logo-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            admin_role,
            basic_role,
            admin,
            basic,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=admin_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, sessions, tmp_path
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        shutil.rmtree(tmp_path, ignore_errors=True)


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_organization(client: TestClient, headers: dict[str, str], slug: str = "fundacion-logo") -> str:
    response = client.post("/api/v1/organizations/", headers=headers, json={"name": "Fundacion Logo", "slug": slug})
    assert response.status_code == 200
    return response.json()["id"]


def upload_logo(client: TestClient, headers: dict[str, str], organization_id: str, content: bytes = TINY_PNG, content_type: str = "image/png", filename: str = "logo.png"):
    return client.post(
        f"/api/v1/organizations/{organization_id}/branding/logo",
        headers=headers,
        files={"upload": (filename, content, content_type)},
    )


def test_upload_logo_stores_file_and_sets_public_url(branding_client):
    client, _sessions, tmp_path = branding_client
    headers = auth(client, "logo-admin@example.com", "Admin12345!")
    organization_id = create_organization(client, headers)

    response = upload_logo(client, headers, organization_id)
    assert response.status_code == 200
    body = response.json()
    assert f"/api/v1/public/branding-logo/{organization_id}" in body["logo_url"]

    stored = tmp_path / "branding" / f"{organization_id}.png"
    assert stored.read_bytes() == TINY_PNG

    served = client.get(f"/api/v1/public/branding-logo/{organization_id}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == TINY_PNG


def test_upload_logo_preserves_existing_colors(branding_client):
    client, sessions, _tmp_path = branding_client
    headers = auth(client, "logo-admin@example.com", "Admin12345!")
    organization_id = create_organization(client, headers)

    put = client.put(
        f"/api/v1/organizations/{organization_id}/branding",
        headers=headers,
        json={"primary_color": "#0A2540", "slogan": "Territorio conectado"},
    )
    assert put.status_code == 200

    response = upload_logo(client, headers, organization_id)
    assert response.status_code == 200

    with sessions() as db:
        row = db.query(OrganizationBranding).filter(OrganizationBranding.organization_id == organization_id).first()
        assert row.primary_color == "#0A2540"
        assert row.slogan == "Territorio conectado"
        assert row.logo_url is not None


def test_upload_logo_rejects_unsupported_type_and_oversize(branding_client):
    client, _sessions, _tmp_path = branding_client
    headers = auth(client, "logo-admin@example.com", "Admin12345!")
    organization_id = create_organization(client, headers)

    wrong_type = upload_logo(client, headers, organization_id, content=b"no soy imagen", content_type="text/plain", filename="logo.txt")
    assert wrong_type.status_code == 422
    assert "Formato" in wrong_type.json()["detail"]

    too_big = upload_logo(client, headers, organization_id, content=b"x" * (organization_service_module.LOGO_MAX_BYTES + 1))
    assert too_big.status_code == 422
    assert "maximo" in too_big.json()["detail"]


def test_upload_logo_requires_permission_and_valid_organization(branding_client):
    client, _sessions, _tmp_path = branding_client
    admin_headers = auth(client, "logo-admin@example.com", "Admin12345!")
    basic_headers = auth(client, "logo-basic@example.com", "Basic12345!")
    organization_id = create_organization(client, admin_headers)

    denied = upload_logo(client, basic_headers, organization_id)
    assert denied.status_code == 403

    missing = upload_logo(client, admin_headers, "no-existe")
    assert missing.status_code == 404


def test_reupload_with_other_format_replaces_previous_file(branding_client):
    client, _sessions, tmp_path = branding_client
    headers = auth(client, "logo-admin@example.com", "Admin12345!")
    organization_id = create_organization(client, headers)

    assert upload_logo(client, headers, organization_id).status_code == 200
    jpeg = upload_logo(client, headers, organization_id, content=b"\xff\xd8\xff\xe0fake-jpeg", content_type="image/jpeg", filename="logo.jpg")
    assert jpeg.status_code == 200

    directory = tmp_path / "branding"
    assert not (directory / f"{organization_id}.png").exists()
    assert (directory / f"{organization_id}.jpg").read_bytes() == b"\xff\xd8\xff\xe0fake-jpeg"

    served = client.get(f"/api/v1/public/branding-logo/{organization_id}")
    assert served.headers["content-type"] == "image/jpeg"


def test_public_logo_404_when_not_uploaded(branding_client):
    client, _sessions, _tmp_path = branding_client
    response = client.get("/api/v1/public/branding-logo/organizacion-sin-logo")
    assert response.status_code == 404


def test_patch_project_links_and_unlinks_organization(branding_client):
    client, _sessions, _tmp_path = branding_client
    admin_headers = auth(client, "logo-admin@example.com", "Admin12345!")
    basic_headers = auth(client, "logo-basic@example.com", "Basic12345!")
    organization_id = create_organization(client, admin_headers)

    denied = client.patch("/api/v1/identity/projects/logo-project", headers=basic_headers, json={"organization_id": organization_id})
    assert denied.status_code == 403

    linked = client.patch("/api/v1/identity/projects/logo-project", headers=admin_headers, json={"organization_id": organization_id})
    assert linked.status_code == 200
    assert linked.json()["organization_id"] == organization_id

    bad_org = client.patch("/api/v1/identity/projects/logo-project", headers=admin_headers, json={"organization_id": "no-existe"})
    assert bad_org.status_code == 404

    bad_project = client.patch("/api/v1/identity/projects/no-existe", headers=admin_headers, json={"organization_id": organization_id})
    assert bad_project.status_code == 404

    unlinked = client.patch("/api/v1/identity/projects/logo-project", headers=admin_headers, json={"organization_id": None})
    assert unlinked.status_code == 200
    assert unlinked.json()["organization_id"] is None


def test_logo_file_for_url_resolves_only_own_urls(branding_client):
    client, _sessions, tmp_path = branding_client
    headers = auth(client, "logo-admin@example.com", "Admin12345!")
    organization_id = create_organization(client, headers)
    assert upload_logo(client, headers, organization_id).status_code == 200

    resolved = organization_service_module.logo_file_for_url(f"http://testserver/api/v1/public/branding-logo/{organization_id}?v=123")
    assert resolved is not None
    assert resolved == tmp_path / "branding" / f"{organization_id}.png"

    assert organization_service_module.logo_file_for_url("https://cdn.example.com/logo.png") is None
    assert organization_service_module.logo_file_for_url(None) is None
