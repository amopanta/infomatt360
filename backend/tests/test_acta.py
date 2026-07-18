import io
import json

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
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.identity import Project, Role, User
from app.models.organization import Organization, OrganizationBranding
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


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


LAYOUT_BLOCKS = {
    "blocks": [
        {"type": "logo", "alignment": "center"},
        {"type": "header", "text": "Acta de {{nombre}}", "level": 1},
        {"type": "table", "field_names": ["nombre", "integrantes"]},
        {"type": "signature", "label": "Firma del coordinador"},
    ]
}


def setup_layout_client(*, with_branding: bool = False) -> tuple:
    """Extiende setup_client() con un BuilderTemplate+componentes y un
    RuntimeRecord real -- lo que necesita el camino del constructor visual
    (ver docs/109), a diferencia del legado que solo necesita project_id."""
    engine = setup_client()
    Sessions = sessionmaker(bind=engine)
    with Sessions() as db:
        template = BuilderTemplate(id="acta-form-template", project_id="acta-project", name="Formulario de prueba", status="published")
        db.add(template)
        db.add_all([
            BuilderComponent(template_id=template.id, component_type="TEXT", name="nombre", label="Nombre del hogar", sort_order=1),
            BuilderComponent(template_id=template.id, component_type="NUMBER", name="integrantes", label="Numero de integrantes", sort_order=2),
        ])
        record = RuntimeRecord(id="acta-record-1", project_id="acta-project", template_id=template.id, status="submitted")
        db.add(record)
        db.add_all([
            RuntimeRecordValue(record_id=record.id, field_name="nombre", field_value_json=json.dumps("Hogar Norte")),
            RuntimeRecordValue(record_id=record.id, field_name="integrantes", field_value_json=json.dumps(4)),
        ])
        if with_branding:
            org = Organization(id="acta-org", name="Organizacion de prueba", slug="acta-org")
            branding = OrganizationBranding(organization_id=org.id, logo_url="https://example.test/logo.png")
            db.add_all([org, branding])
            db.query(Project).filter(Project.id == "acta-project").update({"organization_id": org.id})
        db.commit()
    return engine, Sessions


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


def test_acta_layout_lifecycle_requires_builder_permission():
    engine, _sessions = setup_layout_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            basic_headers = auth(client, "acta-basic@example.com", "Basic12345!")

            denied = client.post(
                "/api/v1/acta-templates/layout",
                headers=basic_headers,
                json={"project_id": "acta-project", "name": "Acta visual", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            assert denied.status_code == 403

            created = client.post(
                "/api/v1/acta-templates/layout",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta visual", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            assert created.status_code == 200, created.text
            assert created.json()["template_id"] == "acta-form-template"
            assert created.json()["layout_json"]
            assert created.json()["html_template"] is None

            listed = client.get("/api/v1/acta-templates/project/acta-project", headers=builder_headers)
            assert listed.status_code == 200
            assert any(item["id"] == created.json()["id"] for item in listed.json())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_render_from_record_uses_participant_and_branding_data():
    engine, _sessions = setup_layout_client(with_branding=True)
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            created = client.post(
                "/api/v1/acta-templates/layout",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta visual", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            template_id = created.json()["id"]

            rendered = client.post(
                f"/api/v1/acta-templates/{template_id}/render-from-record",
                headers=builder_headers,
                json={"record_id": "acta-record-1"},
            )
            assert rendered.status_code == 200, rendered.text
            assert rendered.content[:5] == b"%PDF-"

            reader = PdfReader(io.BytesIO(rendered.content))
            text = reader.pages[0].extract_text()
            assert "Hogar Norte" in text
            assert "Acta de Hogar Norte" in text  # header con el token resuelto
            assert "Nombre del hogar" in text  # label humano, no "nombre" crudo
            assert "Numero de integrantes" in text
            assert "Firma del coordinador" in text

            from app.models.acta import ActaTemplate
            from app.services.acta_service import acta_service

            with _sessions() as db:
                row = db.query(ActaTemplate).filter(ActaTemplate.id == template_id).first()
                html_out = acta_service.render_html_from_blocks(db, row, "acta-record-1")
            assert 'src="https://example.test/logo.png"' in html_out
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_render_from_record_without_branding_omits_logo_gracefully():
    engine, _sessions = setup_layout_client(with_branding=False)
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            created = client.post(
                "/api/v1/acta-templates/layout",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta visual", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            template_id = created.json()["id"]

            rendered = client.post(
                f"/api/v1/acta-templates/{template_id}/render-from-record",
                headers=builder_headers,
                json={"record_id": "acta-record-1"},
            )
            assert rendered.status_code == 200, rendered.text

            from app.models.acta import ActaTemplate
            from app.services.acta_service import acta_service

            with _sessions() as db:
                row = db.query(ActaTemplate).filter(ActaTemplate.id == template_id).first()
                html_out = acta_service.render_html_from_blocks(db, row, "acta-record-1")
            assert "<img" not in html_out
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_render_from_record_rejects_record_from_different_template():
    engine, sessions = setup_layout_client()
    try:
        with sessions() as db:
            other_template = BuilderTemplate(id="acta-other-template", project_id="acta-project", name="Otro formulario", status="published")
            other_record = RuntimeRecord(id="acta-other-record", project_id="acta-project", template_id=other_template.id, status="submitted")
            db.add_all([other_template, other_record])
            db.commit()

        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            created = client.post(
                "/api/v1/acta-templates/layout",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta visual", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            template_id = created.json()["id"]

            rendered = client.post(
                f"/api/v1/acta-templates/{template_id}/render-from-record",
                headers=builder_headers,
                json={"record_id": "acta-other-record"},
            )
            assert rendered.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_acta_layout_template_cannot_mix_with_legacy_html():
    engine, _sessions = setup_layout_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "acta-builder@example.com", "Builder12345!")
            legacy = client.post(
                "/api/v1/acta-templates/",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta legado", "html_template": TEMPLATE_HTML},
            )
            template_id = legacy.json()["id"]

            attempt = client.put(
                f"/api/v1/acta-templates/{template_id}/layout",
                headers=builder_headers,
                json={"project_id": "acta-project", "name": "Acta legado editada", "template_id": "acta-form-template", "layout": LAYOUT_BLOCKS},
            )
            assert attempt.status_code == 422
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
