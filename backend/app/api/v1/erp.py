from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.permissions import require_project_permission
from app.core.permissions import ERP_MANAGE
from app.db.session import get_db
from app.models.builder import BuilderTemplate
from app.models.erp import ErpInventoryItem, ErpPayrollEntry
from app.models.identity import User
from app.schemas.erp import (
    ErpInventoryItemCreate,
    ErpInventoryItemRead,
    ErpInventoryMovementRead,
    ErpPayrollEntryRead,
    ErpTemplateConfigCreate,
    ErpTemplateConfigRead,
)
from app.services.assignment_service import assignment_service
from app.services.erp_service import erp_service

router = APIRouter()


def _template_project_id(db: Session, template_id: str) -> str:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    return template.project_id


def _inventory_item_project_id(db: Session, item_id: str) -> str:
    item = db.query(ErpInventoryItem).filter(ErpInventoryItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item de inventario no encontrado")
    return item.project_id


def _payroll_entry_project_id(db: Session, entry_id: str) -> str:
    entry = db.query(ErpPayrollEntry).filter(ErpPayrollEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Honorario no encontrado")
    return entry.project_id


@router.post("/template-config", response_model=ErpTemplateConfigRead, summary="Vincular una plantilla al motor ERP")
def create_template_config(payload: ErpTemplateConfigCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ErpTemplateConfigRead:
    project_id = _template_project_id(db, payload.template_id)
    require_project_permission(db, current_user.id, project_id, ERP_MANAGE)
    return erp_service.create_template_config(db, payload)


@router.get("/template-config/{template_id}", response_model=ErpTemplateConfigRead | None, summary="Consultar configuracion ERP de una plantilla")
def get_template_config(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ErpTemplateConfigRead | None:
    project_id = _template_project_id(db, template_id)
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return erp_service.get_template_config(db, template_id)


@router.post("/inventory", response_model=ErpInventoryItemRead, summary="Crear item de inventario")
def create_inventory_item(payload: ErpInventoryItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ErpInventoryItemRead:
    require_project_permission(db, current_user.id, payload.project_id, ERP_MANAGE)
    return erp_service.create_inventory_item(db, payload)


@router.get("/inventory/project/{project_id}", response_model=list[ErpInventoryItemRead], summary="Listar inventario de un proyecto")
def list_inventory_items(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ErpInventoryItemRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return erp_service.list_inventory_items(db, project_id)


@router.get("/inventory/{item_id}/movements", response_model=list[ErpInventoryMovementRead], summary="Historial de movimientos de un item")
def list_inventory_movements(item_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ErpInventoryMovementRead]:
    project_id = _inventory_item_project_id(db, item_id)
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return erp_service.list_inventory_movements(db, item_id)


@router.get("/payroll/project/{project_id}", response_model=list[ErpPayrollEntryRead], summary="Listar honorarios acumulados de un proyecto")
def list_payroll_entries(project_id: str, gestor_user_id: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ErpPayrollEntryRead]:
    if not assignment_service.user_has_project_access(db, current_user.id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return erp_service.list_payroll_entries(db, project_id, gestor_user_id)


@router.patch("/payroll/{entry_id}/mark-paid", response_model=ErpPayrollEntryRead, summary="Marcar un honorario como pagado")
def mark_payroll_entry_paid(entry_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ErpPayrollEntryRead:
    project_id = _payroll_entry_project_id(db, entry_id)
    require_project_permission(db, current_user.id, project_id, ERP_MANAGE)
    return erp_service.mark_payroll_entry_paid(db, entry_id)
