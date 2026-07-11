from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ErpTemplateConfigCreate(BaseModel):
    template_id: str
    sku_field_name: str
    quantity_field_name: str
    fee_amount: Decimal = Field(ge=0)


class ErpTemplateConfigRead(BaseModel):
    id: str
    template_id: str
    sku_field_name: str
    quantity_field_name: str
    fee_amount: Decimal
    created_at: datetime


class ErpInventoryItemCreate(BaseModel):
    project_id: str
    sku: str
    name: str
    unit: str = "unidad"
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0)


class ErpInventoryItemRead(BaseModel):
    id: str
    project_id: str
    sku: str
    name: str
    unit: str
    quantity_on_hand: Decimal
    created_at: datetime


class ErpInventoryMovementRead(BaseModel):
    id: str
    item_id: str
    quantity_delta: Decimal
    reference_record_id: str | None = None
    reason: str
    created_at: datetime


class ErpPayrollEntryRead(BaseModel):
    id: str
    project_id: str
    gestor_user_id: str
    amount: Decimal
    reference_record_id: str | None = None
    status: str
    created_at: datetime
    paid_at: datetime | None = None
