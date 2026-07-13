import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.models.builder_public_link import BuilderPublicLink
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        project = Project(id="pf-project", name="Formularios publicos")
        builder_role = Role(id="pf-builder-role", name="Disenador", permissions="builder.write")
        outsider_role = Role(id="pf-outsider-role", name="Sin permiso", permissions="records.read")
        builder_user = User(id="pf-builder", full_name="Disenador", document_id="pf-builder-doc", email="pf-builder@example.com", password_hash=hash_password("Builder12345!"))
        outsider = User(id="pf-outsider", full_name="Sin permiso", document_id="pf-outsider-doc", email="pf-outsider@example.com", password_hash=hash_password("Outsider12345!"))

        published = BuilderTemplate(id="pf-template-published", project_id=project.id, name="Encuesta feria comercial", status="published")
        draft = BuilderTemplate(id="pf-template-draft", project_id=project.id, name="Borrador", status="draft")

        page = BuilderPage(id="pf-page", template_id=published.id, title="Pagina 1", sort_order=1)
        section = BuilderSection(id="pf-section", page_id=page.id, title="Datos", sort_order=1)
        row = BuilderRow(id="pf-row", section_id=section.id, sort_order=1)
        column = BuilderColumn(id="pf-column", row_id=row.id, desktop_width=12, sort_order=1)
        component = BuilderComponent(id="pf-component", template_id=published.id, column_id=column.id, component_type="TEXT", name="nombre_completo", label="Nombre completo", sort_order=1)

        db.add_all([
            project, builder_role, outsider_role, builder_user, outsider,
            published, draft, page, section, row, column, component,
            UserProjectAssignment(user_id=builder_user.id, project_id=project.id, role_id=builder_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_creating_a_public_link_requires_builder_write_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "pf-outsider@example.com", "Outsider12345!")
            denied = client.post("/api/v1/public-forms/links", headers=outsider_headers, json={"template_id": "pf-template-published"})
            assert denied.status_code == 403

            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            created = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-published", "label": "Feria Bogota"})
            assert created.status_code == 200, created.text
            body = created.json()
            assert body["token"]
            assert body["max_submissions"] is None
            assert body["submission_count"] == 0
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_creating_a_public_link_for_a_draft_template_is_rejected():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            response = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-draft"})
            assert response.status_code == 400
            assert "publicada" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_public_form_capture_and_submission_end_to_end_without_authentication():
    """El caso principal: alguien SIN cuenta abre el enlace y envia una respuesta."""
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            issued = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-published"}).json()
            token = issued["token"]

            # Sin ningun header de autenticacion.
            form = client.get(f"/api/v1/public-forms/{token}")
            assert form.status_code == 200, form.text
            template = form.json()
            assert template["template_id"] == "pf-template-published"
            assert template["pages"][0]["sections"][0]["rows"][0]["columns"][0]["components"][0]["name"] == "nombre_completo"

            submitted = client.post(
                f"/api/v1/public-forms/{token}/submit",
                json={"values": [{"field_name": "nombre_completo", "field_value_json": json.dumps("Carlos Gomez")}]},
            )
            assert submitted.status_code == 200, submitted.text
            body = submitted.json()
            assert body["submitted"] is True

            with sessions() as db:
                record = db.get(RuntimeRecord, body["record_id"])
                assert record is not None
                assert record.project_id == "pf-project"
                assert record.submitted_by is None
                link = db.query(BuilderPublicLink).filter(BuilderPublicLink.token_hash != None).first()  # noqa: E711
                assert link.submission_count == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_public_form_rejects_unknown_expired_or_revoked_token():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            unknown = client.get("/api/v1/public-forms/does-not-exist-token")
            assert unknown.status_code == 400

            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            issued = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-published"}).json()

            with sessions() as db:
                link = db.query(BuilderPublicLink).filter(BuilderPublicLink.id == issued["id"]).one()
                link.revoked_at = utc_now()
                db.commit()

            revoked = client.get(f"/api/v1/public-forms/{issued['token']}")
            assert revoked.status_code == 400
            assert "revocado" in revoked.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_public_form_enforces_max_submissions_limit():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            issued = client.post(
                "/api/v1/public-forms/links",
                headers=builder_headers,
                json={"template_id": "pf-template-published", "max_submissions": 1},
            ).json()
            token = issued["token"]

            first = client.post(f"/api/v1/public-forms/{token}/submit", json={"values": [{"field_name": "nombre_completo", "field_value_json": json.dumps("Uno")}]})
            assert first.status_code == 200

            second = client.post(f"/api/v1/public-forms/{token}/submit", json={"values": [{"field_name": "nombre_completo", "field_value_json": json.dumps("Dos")}]})
            assert second.status_code in (400, 409)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_revoking_a_public_link_blocks_further_access():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            issued = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-published"}).json()

            revoke = client.post(f"/api/v1/public-forms/links/{issued['id']}/revoke", headers=builder_headers)
            assert revoke.status_code == 200
            assert revoke.json()["revoked_at"] is not None

            blocked = client.get(f"/api/v1/public-forms/{issued['token']}")
            assert blocked.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_listing_and_revoking_links_requires_builder_write_permission():
    engine, _sessions = setup_client()
    try:
        with TestClient(app) as client:
            builder_headers = auth(client, "pf-builder@example.com", "Builder12345!")
            outsider_headers = auth(client, "pf-outsider@example.com", "Outsider12345!")
            issued = client.post("/api/v1/public-forms/links", headers=builder_headers, json={"template_id": "pf-template-published"}).json()

            denied_list = client.get("/api/v1/public-forms/links/pf-template-published", headers=outsider_headers)
            assert denied_list.status_code == 403

            allowed_list = client.get("/api/v1/public-forms/links/pf-template-published", headers=builder_headers)
            assert allowed_list.status_code == 200
            assert len(allowed_list.json()) == 1
            assert "token" not in allowed_list.json()[0]

            denied_revoke = client.post(f"/api/v1/public-forms/links/{issued['id']}/revoke", headers=outsider_headers)
            assert denied_revoke.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
