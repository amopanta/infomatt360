"""Motor contable headless (inventario + honorarios de gestor).

Alcance minimo definido a partir de la especificacion original ("Modulo
Contable y Liquidacion Transaccional"): cuando un registro de formulario
pasa a estado "approved", se descuenta stock de un insumo por SKU y se
acredita un honorario de tarifa plana al gestor que capturo el registro, en
una sola transaccion. Si el stock es insuficiente, la aprobacion completa se
bloquea (ver `app.services.erp_service`).

Deliberadamente fuera de alcance: contabilidad general, facturacion,
impuestos, nomina real (deducciones/seguridad social), compras/proveedores,
multiples bodegas por proyecto y desembolso bancario.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid4())


class ErpTemplateConfig(Base):
    """Vincula una plantilla del Builder al motor ERP.

    Una plantilla sin fila aqui no dispara ninguna liquidacion al aprobarse
    (la mayoria de formularios no representan una entrega de insumos).
    """

    __tablename__ = "erp_template_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    template_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    sku_field_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity_field_name: Mapped[str] = mapped_column(String(180), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ErpInventoryItem(Base):
    """Saldo actual de un insumo (SKU) en la bodega regional de un proyecto.

    Una sola bodega por proyecto en este alcance minimo (sin subbodegas ni
    transferencias entre ellas).
    """

    __tablename__ = "erp_inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), default="unidad", nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ErpInventoryMovement(Base):
    """Ledger inmutable de movimientos de inventario.

    Nunca se edita ni se borra una fila existente: cada ajuste (entrega,
    alta manual) es una fila nueva. `quantity_on_hand` en `ErpInventoryItem`
    es un saldo materializado que se mantiene en el mismo commit que la fila
    de movimiento correspondiente.
    """

    __tablename__ = "erp_inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reference_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(40), default="manual_adjustment", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ErpPayrollEntry(Base):
    """Ledger inmutable de honorarios acumulados por gestor.

    `status="accrued"` es el estado que genera la liquidacion automatica;
    `status="paid"` se marca manualmente (sin integracion de desembolso
    bancario en este alcance minimo).
    """

    __tablename__ = "erp_payroll_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gestor_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="accrued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
