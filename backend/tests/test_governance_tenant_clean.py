import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.erp import ErpInventoryItem, ErpInventoryMovement
from app.models.files import FileAsset
from app.models.identity import Project, Role, User
from app.models.organization import Organization
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.services.mfa_service import mfa_service


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    secret = mfa_service.new_secret()
    with sessions() as db:
        organization = Organization(id="org-gov", name="Org Gov", slug="org-gov")
        other_organization = Organization(id="org-other", name="Org Other", slug="org-other")
        project = Project(id="gov-project", name="Gov Project", organization_id="org-gov")
        other_project = Project(id="other-project", name="Other Project", organization_id="org-other")

        clean_role = Role(id="gov-clean-role", name="Alta gerencia", permissions="organizations.tenant_clean")
        outsider_role = Role(id="gov-outsider-role", name="Sin permiso", permissions="records.read")

        admin = User(
            id="gov-admin",
            full_name="Admin Gov",
            document_id="gov-admin-doc",
            email="gov-admin@example.com",
            password_hash=hash_password("AdminPassword123"),
            mfa_enabled=True,
            mfa_secret_encrypted=mfa_service.encrypt_secret(secret),
        )
        outsider = User(id="gov-outsider", full_name="Outsider", document_id="gov-outsider-doc", email="gov-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        unaffiliated = User(
            id="gov-unaffiliated",
            full_name="Sin org",
            document_id="gov-unaffiliated-doc",
            email="gov-unaffiliated@example.com",
            password_hash=hash_password("Unaffiliated12345!"),
            mfa_enabled=True,
            mfa_secret_encrypted=mfa_service.encrypt_secret(secret),
        )

        db.add_all([
            organization,
            other_organization,
            project,
            other_project,
            clean_role,
            outsider_role,
            admin,
            outsider,
            unaffiliated,
            UserProjectAssignment(user_id=admin.id, project_id=project.id, role_id=clean_role.id, status="active"),
            UserProjectAssignment(user_id=outsider.id, project_id=project.id, role_id=outsider_role.id, status="active"),
        ])

        db.add_all([
            Participant(id="gov-participant-1", project_id="gov-project", full_name="Beneficiario 1"),
            RuntimeRecord(id="gov-record-1", project_id="gov-project", template_id="tpl-1"),
            RuntimeRecordValue(id="gov-value-1", record_id="gov-record-1", field_name="nombre", field_value_json='"x"'),
            FileAsset(id="gov-file-1", project_id="gov-project", asset_type="FILE", original_name="a.txt", storage_provider="local", storage_path="/tmp/a.txt", size_bytes=1, checksum="abc"),
            ErpInventoryItem(id="gov-item-1", project_id="gov-project", sku="KIT-1", name="Kit", unit="unidad"),
            ErpInventoryMovement(id="gov-movement-1", item_id="gov-item-1", quantity_delta=1, reason="manual_adjustment"),
            Participant(id="other-participant-1", project_id="other-project", full_name="Otro beneficiario"),
        ])
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, sessions, secret


def auth(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def auth_with_mfa(client: TestClient, email: str, password: str, secret: str) -> dict[str, str]:
    challenge = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert challenge.status_code == 200
    body = challenge.json()
    assert body["mfa_required"] is True
    verified = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_token": body["mfa_challenge_token"], "code": totp_for(secret)},
    )
    assert verified.status_code == 200
    return {"Authorization": f"Bearer {verified.json()['access_token']}"}


def totp_for(secret: str) -> str:
    return mfa_service._totp(secret, int(time.time()) // 30)


def action_totp_for(secret: str) -> str:
    """Codigo TOTP para una segunda verificacion tras el login (evita reutilizar el mismo contador)."""
    return mfa_service._totp(secret, int(time.time()) // 30 + 1)


def test_tenant_clean_requires_permission():
    engine, sessions, secret = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "gov-outsider@example.com", "Outsider12345!")
            response = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "org-gov", "totp_code": "000000"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_tenant_clean_rejects_unaffiliated_organization():
    engine, sessions, secret = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth_with_mfa(client, "gov-unaffiliated@example.com", "Unaffiliated12345!", secret)
            response = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "org-gov", "totp_code": action_totp_for(secret)},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_tenant_clean_rejects_wrong_slug_confirmation():
    engine, sessions, secret = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth_with_mfa(client, "gov-admin@example.com", "AdminPassword123", secret)
            response = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "wrong-slug", "totp_code": action_totp_for(secret)},
            )
            assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_tenant_clean_rejects_invalid_totp():
    engine, sessions, secret = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth_with_mfa(client, "gov-admin@example.com", "AdminPassword123", secret)
            response = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "org-gov", "totp_code": "000000"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_tenant_clean_purges_operational_data_and_protects_master_tables():
    engine, sessions, secret = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth_with_mfa(client, "gov-admin@example.com", "AdminPassword123", secret)
            code = action_totp_for(secret)
            response = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "org-gov", "totp_code": code},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["projects_purged"] == ["gov-project"]
            assert body["deleted_counts"]["participants"] == 1
            assert body["deleted_counts"]["runtime_records"] == 1
            assert body["deleted_counts"]["runtime_record_values"] == 1
            assert body["deleted_counts"]["file_assets"] == 1
            assert "erp_inventory_movements" not in body["deleted_counts"]

            with sessions() as db:
                assert db.query(Participant).filter(Participant.project_id == "gov-project").count() == 0
                assert db.query(RuntimeRecord).filter(RuntimeRecord.project_id == "gov-project").count() == 0
                assert db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == "gov-record-1").count() == 0
                assert db.query(FileAsset).filter(FileAsset.project_id == "gov-project").count() == 0

                # Protegido: todo el modulo ERP (ledger inmutable + inventario maestro)
                assert db.query(ErpInventoryItem).filter(ErpInventoryItem.id == "gov-item-1").count() == 1
                assert db.query(ErpInventoryMovement).filter(ErpInventoryMovement.id == "gov-movement-1").count() == 1
                # Protegido: usuarios y asignaciones
                assert db.query(User).filter(User.id == "gov-admin").count() == 1
                assert db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == "gov-admin").count() == 1
                # Otra organizacion no se toca
                assert db.query(Participant).filter(Participant.project_id == "other-project").count() == 1

            # Un segundo intento con el mismo codigo TOTP debe fallar (ya consumido)
            second = client.post(
                "/api/v1/organizations/org-gov/tenant-clean",
                headers=headers,
                json={"confirm_slug": "org-gov", "totp_code": code},
            )
            assert second.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
