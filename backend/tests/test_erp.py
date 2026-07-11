import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assignment import UserProjectAssignment
from app.models.builder import BuilderTemplate
from app.models.erp import ErpInventoryItem, ErpInventoryMovement, ErpPayrollEntry, ErpTemplateConfig
from app.models.identity import Project, Role, User
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue


def setup_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with sessions() as db:
        approver = User(id="erp-approver", full_name="Aprobador", document_id="erp-approver-doc", email="erp-approver@example.com", password_hash=hash_password("Approver12345!"))
        gestor = User(id="erp-gestor", full_name="Gestor", document_id="erp-gestor-doc", email="erp-gestor@example.com", password_hash=hash_password("Gestor12345!"))
        manager = User(id="erp-manager", full_name="Administrador ERP", document_id="erp-manager-doc", email="erp-manager@example.com", password_hash=hash_password("Manager12345!"))
        outsider = User(id="erp-outsider", full_name="Sin acceso", document_id="erp-outsider-doc", email="erp-outsider@example.com", password_hash=hash_password("Outsider12345!"))
        project = Project(id="erp-project", name="Proyecto ERP")
        approver_role = Role(id="erp-approver-role", name="Aprobador", permissions="records.approve,records.read")
        manager_role = Role(id="erp-manager-role", name="ERP Manager", permissions="erp.manage,records.read")
        outsider_role = Role(id="erp-outsider-role", name="Sin permiso", permissions="records.read")
        template = BuilderTemplate(id="erp-template", project_id=project.id, name="Entrega de kits", status="published")
        config = ErpTemplateConfig(template_id=template.id, sku_field_name="sku_kit", quantity_field_name="cantidad", fee_amount="15000.00")
        item = ErpInventoryItem(id="erp-item-kit", project_id=project.id, sku="KIT-001", name="Kit de herramientas", unit="unidad", quantity_on_hand="10")

        db.add_all([
            approver, gestor, manager, outsider, project,
            approver_role, manager_role, outsider_role,
            template, config, item,
            UserProjectAssignment(user_id=approver.id, project_id=project.id, role_id=approver_role.id, status="active"),
            UserProjectAssignment(user_id=manager.id, project_id=project.id, role_id=manager_role.id, status="active"),
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


def _create_record(sessions, record_id: str, quantity: str, submitted_by: str = "erp-gestor") -> None:
    with sessions() as db:
        record = RuntimeRecord(id=record_id, project_id="erp-project", template_id="erp-template", status="submitted", submitted_by=submitted_by)
        db.add(record)
        db.add(RuntimeRecordValue(record_id=record_id, field_name="sku_kit", field_value_json=json.dumps("KIT-001")))
        db.add(RuntimeRecordValue(record_id=record_id, field_name="cantidad", field_value_json=json.dumps(quantity)))
        db.commit()


def test_approving_record_settles_inventory_and_payroll():
    engine, sessions = setup_client()
    try:
        _create_record(sessions, "erp-record-ok", "3")
        with TestClient(app) as client:
            headers = auth(client, "erp-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "erp-project", "record_id": "erp-record-ok", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                record = db.get(RuntimeRecord, "erp-record-ok")
                assert record.status == "approved"

                item = db.get(ErpInventoryItem, "erp-item-kit")
                assert item.quantity_on_hand == 7

                movements = db.query(ErpInventoryMovement).filter(ErpInventoryMovement.item_id == "erp-item-kit").all()
                assert len(movements) == 1
                assert movements[0].quantity_delta == -3
                assert movements[0].reference_record_id == "erp-record-ok"

                payroll = db.query(ErpPayrollEntry).filter(ErpPayrollEntry.reference_record_id == "erp-record-ok").first()
                assert payroll is not None
                assert payroll.gestor_user_id == "erp-gestor"
                assert payroll.amount == 15000
                assert payroll.status == "accrued"
    finally:
        engine.dispose()


def test_approving_record_with_insufficient_stock_blocks_approval_and_rolls_back():
    engine, sessions = setup_client()
    try:
        _create_record(sessions, "erp-record-over", "99")
        with TestClient(app) as client:
            headers = auth(client, "erp-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "erp-project", "record_id": "erp-record-over", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 400
            assert "Stock insuficiente" in response.json()["detail"]

            with sessions() as db:
                record = db.get(RuntimeRecord, "erp-record-over")
                assert record.status == "submitted"

                item = db.get(ErpInventoryItem, "erp-item-kit")
                assert item.quantity_on_hand == 10

                assert db.query(ErpInventoryMovement).filter(ErpInventoryMovement.item_id == "erp-item-kit").count() == 0
                assert db.query(ErpPayrollEntry).filter(ErpPayrollEntry.reference_record_id == "erp-record-over").count() == 0
    finally:
        engine.dispose()


def test_approving_record_without_erp_template_config_is_a_noop():
    engine, sessions = setup_client()
    try:
        with sessions() as db:
            plain_template = BuilderTemplate(id="erp-plain-template", project_id="erp-project", name="Formulario normal", status="published")
            record = RuntimeRecord(id="erp-record-plain", project_id="erp-project", template_id="erp-plain-template", status="submitted", submitted_by="erp-gestor")
            db.add_all([plain_template, record])
            db.commit()

        with TestClient(app) as client:
            headers = auth(client, "erp-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=headers,
                json={"project_id": "erp-project", "record_id": "erp-record-plain", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                assert db.query(ErpPayrollEntry).count() == 0
    finally:
        engine.dispose()


def test_create_inventory_item_requires_erp_manage_permission():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            outsider_headers = auth(client, "erp-outsider@example.com", "Outsider12345!")
            response = client.post(
                "/api/v1/erp/inventory",
                headers=outsider_headers,
                json={"project_id": "erp-project", "sku": "KIT-002", "name": "Kit medico", "unit": "unidad", "quantity_on_hand": "5"},
            )
            assert response.status_code == 403

            manager_headers = auth(client, "erp-manager@example.com", "Manager12345!")
            response = client.post(
                "/api/v1/erp/inventory",
                headers=manager_headers,
                json={"project_id": "erp-project", "sku": "KIT-002", "name": "Kit medico", "unit": "unidad", "quantity_on_hand": "5"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert float(body["quantity_on_hand"]) == 5

            with sessions() as db:
                movement = db.query(ErpInventoryMovement).filter(ErpInventoryMovement.item_id == body["id"]).first()
                assert movement is not None
                assert movement.reason == "alta_inicial"
    finally:
        engine.dispose()


def test_create_inventory_item_rejects_duplicate_sku_in_same_project():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            manager_headers = auth(client, "erp-manager@example.com", "Manager12345!")
            response = client.post(
                "/api/v1/erp/inventory",
                headers=manager_headers,
                json={"project_id": "erp-project", "sku": "KIT-001", "name": "Duplicado", "unit": "unidad", "quantity_on_hand": "1"},
            )
            assert response.status_code == 409
    finally:
        engine.dispose()


def test_list_inventory_and_payroll_requires_project_access():
    engine, sessions = setup_client()
    try:
        with TestClient(app) as client:
            headers = auth(client, "erp-manager@example.com", "Manager12345!")
            response = client.get("/api/v1/erp/inventory/project/erp-project", headers=headers)
            assert response.status_code == 200
            assert any(item["sku"] == "KIT-001" for item in response.json())

            response = client.get("/api/v1/erp/payroll/project/erp-project", headers=headers)
            assert response.status_code == 200

            response = client.get("/api/v1/erp/inventory/project/other-project", headers=headers)
            assert response.status_code == 403
    finally:
        engine.dispose()


def test_mark_payroll_entry_paid():
    engine, sessions = setup_client()
    try:
        _create_record(sessions, "erp-record-pay", "1")
        with TestClient(app) as client:
            approver_headers = auth(client, "erp-approver@example.com", "Approver12345!")
            response = client.post(
                "/api/v1/review/actions",
                headers=approver_headers,
                json={"project_id": "erp-project", "record_id": "erp-record-pay", "to_status": "approved", "action": "approve"},
            )
            assert response.status_code == 200, response.text

            with sessions() as db:
                entry = db.query(ErpPayrollEntry).filter(ErpPayrollEntry.reference_record_id == "erp-record-pay").first()
                entry_id = entry.id

            manager_headers = auth(client, "erp-manager@example.com", "Manager12345!")
            response = client.patch(f"/api/v1/erp/payroll/{entry_id}/mark-paid", headers=manager_headers)
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "paid"

            response = client.patch(f"/api/v1/erp/payroll/{entry_id}/mark-paid", headers=manager_headers)
            assert response.status_code == 409
    finally:
        engine.dispose()
