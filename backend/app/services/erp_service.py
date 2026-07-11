"""Motor contable headless: liquidacion transaccional al aprobar un registro.

Cuando un `RuntimeRecord` pasa a estado "approved" (ver
`app.services.review_service.apply_action`), si su plantilla tiene un
`ErpTemplateConfig`, se descuenta stock del SKU indicado y se acredita el
honorario de tarifa plana al gestor que capturo el registro, en la misma
transaccion de base de datos que el cambio de estado.

Bloqueo por stock insuficiente: `settle_record` lanza `ValueError` *antes*
de cualquier `db.commit()` (la llamada ocurre dentro de
`review_service.apply_action`, que solo confirma al final). Como la sesion
de SQLAlchemy no aplica cambios hasta el commit, una excepcion aqui descarta
tambien el cambio de estado del registro y las filas de auditoria ya
agregadas en la misma transaccion -- el mismo efecto que el ROLLBACK ACID
descrito en la especificacion original, sin necesitar una transaccion
explicita separada.
"""

import json
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.erp import ErpInventoryItem, ErpInventoryMovement, ErpPayrollEntry, ErpTemplateConfig
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.erp import (
    ErpInventoryItemCreate,
    ErpInventoryItemRead,
    ErpInventoryMovementRead,
    ErpPayrollEntryRead,
    ErpTemplateConfigCreate,
    ErpTemplateConfigRead,
)


def _item_to_read(row: ErpInventoryItem) -> ErpInventoryItemRead:
    return ErpInventoryItemRead(
        id=row.id, project_id=row.project_id, sku=row.sku, name=row.name,
        unit=row.unit, quantity_on_hand=row.quantity_on_hand, created_at=row.created_at,
    )


def _movement_to_read(row: ErpInventoryMovement) -> ErpInventoryMovementRead:
    return ErpInventoryMovementRead(
        id=row.id, item_id=row.item_id, quantity_delta=row.quantity_delta,
        reference_record_id=row.reference_record_id, reason=row.reason, created_at=row.created_at,
    )


def _payroll_to_read(row: ErpPayrollEntry) -> ErpPayrollEntryRead:
    return ErpPayrollEntryRead(
        id=row.id, project_id=row.project_id, gestor_user_id=row.gestor_user_id, amount=row.amount,
        reference_record_id=row.reference_record_id, status=row.status, created_at=row.created_at, paid_at=row.paid_at,
    )


def _config_to_read(row: ErpTemplateConfig) -> ErpTemplateConfigRead:
    return ErpTemplateConfigRead(
        id=row.id, template_id=row.template_id, sku_field_name=row.sku_field_name,
        quantity_field_name=row.quantity_field_name, fee_amount=row.fee_amount, created_at=row.created_at,
    )


def _parse_decimal(raw_json: str, field_label: str) -> Decimal:
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        value = raw_json
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"El campo '{field_label}' no tiene un valor numerico valido para liquidacion ERP") from exc


def _parse_text(raw_json: str) -> str:
    try:
        value = json.loads(raw_json)
    except json.JSONDecodeError:
        return raw_json
    return str(value)


class ErpService:
    def settle_record(self, db: Session, record: RuntimeRecord) -> None:
        """Ejecuta la liquidacion de un registro aprobado, si su plantilla esta configurada.

        No hace nada (return silencioso) si la plantilla no tiene
        `ErpTemplateConfig`: la mayoria de formularios no representan una
        entrega de insumos. Lanza `ValueError` si la liquidacion no puede
        completarse (SKU inexistente, stock insuficiente, campos faltantes),
        lo que el llamador debe dejar propagar sin capturar antes del commit.
        """
        config = db.query(ErpTemplateConfig).filter(ErpTemplateConfig.template_id == record.template_id).first()
        if config is None:
            return

        values = {
            row.field_name: row.field_value_json
            for row in db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record.id).all()
        }
        sku_raw = values.get(config.sku_field_name)
        quantity_raw = values.get(config.quantity_field_name)
        if sku_raw is None or quantity_raw is None:
            raise ValueError(
                f"El registro no tiene valores para los campos ERP configurados "
                f"('{config.sku_field_name}'/'{config.quantity_field_name}')"
            )
        sku = _parse_text(sku_raw)
        quantity = _parse_decimal(quantity_raw, config.quantity_field_name)
        if quantity <= 0:
            raise ValueError("La cantidad entregada debe ser mayor que cero")

        item = db.query(ErpInventoryItem).filter(
            ErpInventoryItem.project_id == record.project_id,
            ErpInventoryItem.sku == sku,
        ).first()
        if item is None:
            raise ValueError(f"No existe un item de inventario con SKU '{sku}' en este proyecto")
        if item.quantity_on_hand < quantity:
            raise ValueError(
                f"Stock insuficiente para el SKU '{sku}': disponible {item.quantity_on_hand}, solicitado {quantity}"
            )

        item.quantity_on_hand -= quantity
        db.add(ErpInventoryMovement(item_id=item.id, quantity_delta=-quantity, reference_record_id=record.id, reason="entrega_aprobada"))

        if record.submitted_by:
            db.add(ErpPayrollEntry(
                project_id=record.project_id,
                gestor_user_id=record.submitted_by,
                amount=config.fee_amount,
                reference_record_id=record.id,
                status="accrued",
            ))

    # --- Configuracion de plantilla ---

    def create_template_config(self, db: Session, payload: ErpTemplateConfigCreate) -> ErpTemplateConfigRead:
        existing = db.query(ErpTemplateConfig).filter(ErpTemplateConfig.template_id == payload.template_id).first()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta plantilla ya tiene configuracion ERP")
        row = ErpTemplateConfig(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return _config_to_read(row)

    def get_template_config(self, db: Session, template_id: str) -> ErpTemplateConfigRead | None:
        row = db.query(ErpTemplateConfig).filter(ErpTemplateConfig.template_id == template_id).first()
        return _config_to_read(row) if row else None

    # --- Inventario ---

    def create_inventory_item(self, db: Session, payload: ErpInventoryItemCreate) -> ErpInventoryItemRead:
        existing = db.query(ErpInventoryItem).filter(
            ErpInventoryItem.project_id == payload.project_id,
            ErpInventoryItem.sku == payload.sku,
        ).first()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un item de inventario con este SKU en el proyecto")
        row = ErpInventoryItem(**payload.model_dump())
        db.add(row)
        db.flush()
        if row.quantity_on_hand:
            db.add(ErpInventoryMovement(item_id=row.id, quantity_delta=row.quantity_on_hand, reason="alta_inicial"))
        db.commit()
        db.refresh(row)
        return _item_to_read(row)

    def list_inventory_items(self, db: Session, project_id: str) -> list[ErpInventoryItemRead]:
        rows = db.query(ErpInventoryItem).filter(ErpInventoryItem.project_id == project_id).order_by(ErpInventoryItem.sku).all()
        return [_item_to_read(row) for row in rows]

    def get_inventory_item(self, db: Session, item_id: str) -> ErpInventoryItemRead | None:
        row = db.query(ErpInventoryItem).filter(ErpInventoryItem.id == item_id).first()
        return _item_to_read(row) if row else None

    def list_inventory_movements(self, db: Session, item_id: str) -> list[ErpInventoryMovementRead]:
        rows = db.query(ErpInventoryMovement).filter(ErpInventoryMovement.item_id == item_id).order_by(ErpInventoryMovement.created_at.desc()).all()
        return [_movement_to_read(row) for row in rows]

    # --- Honorarios ---

    def list_payroll_entries(self, db: Session, project_id: str, gestor_user_id: str | None = None) -> list[ErpPayrollEntryRead]:
        query = db.query(ErpPayrollEntry).filter(ErpPayrollEntry.project_id == project_id)
        if gestor_user_id:
            query = query.filter(ErpPayrollEntry.gestor_user_id == gestor_user_id)
        rows = query.order_by(ErpPayrollEntry.created_at.desc()).all()
        return [_payroll_to_read(row) for row in rows]

    def mark_payroll_entry_paid(self, db: Session, entry_id: str) -> ErpPayrollEntryRead:
        row = db.query(ErpPayrollEntry).filter(ErpPayrollEntry.id == entry_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Honorario no encontrado")
        if row.status == "paid":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El honorario ya esta marcado como pagado")
        row.status = "paid"
        row.paid_at = utc_now()
        db.commit()
        db.refresh(row)
        return _payroll_to_read(row)


erp_service = ErpService()
