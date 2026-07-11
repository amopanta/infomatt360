import io

from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.identity import Project, Role, User


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="acta-project", name="Acta Project")
        builder_role = Role(id="acta-builder-role", name="Builder", permissions="builder.write")
        basic_role = Role(id="acta-basic-role", name="Basico", permissions="records.read")
        builder = User(id="acta-builder", full_name="Builder", document_id="acta-builder-doc", email="acta-builder@example.com", password_hash=hash_password("Builder12345!"))
        basic = User(id="acta-basic", full_name="Basic", document_id="acta-basic-doc", email="acta-basic@example.com", password_hash=hash_password("Basic12345!"))
        db.add_all([
            project,
            builder_role,
            basic_role,
            builder,
            basic,
            UserProjectAssignment(user_id=builder.id, project_id=project.id, role_id=builder_role.id, status="active"),
            UserProjectAssignment(user_id=basic.id, project_id=project.id, role_id=basic_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


TEMPLATE_HTML = """
<html><body>
<h1>Acta de entrega</h1>
<p>Beneficiario: {{ nombre_beneficiario }}</p>
<p>Fecha: {{ fecha }}</p>
</body></html>
"""


def test_acta_lifecycle_requires_builder_permission():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            basic_headers = auth(client, "acta-basic@example.com", "Basic12345!")

            denied = client.post(
                "/api/v1/acta-templates/",
                headers=basic_headers,
                json={"project_id": "acta-project", "name": "Acta de entrega", "html_template": TEMPLATE_HTML},
            )
            assert denied.status_code == 403

            created = client.post(
                "/api/v1/acta-templates/",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta de entrega", "html_template": TEMPLATE_HTML},
            )
            assert created.status_code == 200
            template_id = created.json()["id"]

            listed = client.get("/api/v1/acta-templates/project/acta-project", headers=builder_headers)
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == template_id
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_render_produces_real_pdf_with_substituted_data():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            created = client.post(
                "/api/v1/acta-templates/",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta de entrega", "html_template": TEMPLATE_HTML},
            )
            template_id = created.json()["id"]

            rendered = client.post(
                f"/api/v1/acta-templates/{template_id}/render",
                headers=builder_headers,
                json={"data": {"nombre_beneficiario": "Ana Gomez Rodriguez", "fecha": "10/07/2026"}},
            )
            assert rendered.status_code == 200
            assert rendered.headers["content-type"] == "application/pdf"
            assert rendered.content[:5] == b"%PDF-"

            reader = PdfReader(io.BytesIO(rendered.content))
            text = reader.pages[0].extract_text()
            assert "Ana Gomez Rodriguez" in text
            assert "10/07/2026" in text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_render_escapes_html_injection_in_data():
    # La verificacion se hace sobre el HTML compilado (antes de xhtml2pdf): un
    # dato malicioso no debe poder cerrar/inyectar etiquetas en la estructura
    # del acta. Extraer texto plano de un PDF no distingue "texto escapado
    # visible" de "markup real no renderizado", asi que no sirve para probar
    # esto de forma confiable.
    from app.models.acta import ActaTemplate
    from app.services.acta_service import acta_service

    template = ActaTemplate(project_id="acta-project", name="Acta", html_template=TEMPLATE_HTML)
    compiled = acta_service.render_html(template, {"nombre_beneficiario": "</p><h1>HACKED</h1><p>", "fecha": "10/07/2026"})

    assert "<h1>HACKED</h1>" not in compiled
    assert "&lt;h1&gt;HACKED&lt;/h1&gt;" in compiled


def test_acta_render_rejects_malformed_template():
    engine = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            created = client.post(
                "/api/v1/acta-templates/",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta rota", "html_template": "<p>{{ nombre_beneficiario"},
            )
            template_id = created.json()["id"]

            rendered = client.post(
                f"/api/v1/acta-templates/{template_id}/render",
                headers=builder_headers,
                json={"data": {"nombre_beneficiario": "Ana"}},
            )
            assert rendered.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
