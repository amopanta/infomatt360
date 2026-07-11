from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.builder_access import require_page_access, require_row_access, require_section_access, require_template_access
from app.db.session import get_db
from app.models.identity import User
from app.schemas.builder_layout import BuilderColumnCreate, BuilderColumnRead, BuilderPageCreate, BuilderPageRead, BuilderRowCreate, BuilderRowRead, BuilderSectionCreate, BuilderSectionRead
from app.services.builder_layout_service import builder_layout_service

router = APIRouter()


@router.post("/pages", response_model=BuilderPageRead)
def create_page(payload: BuilderPageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderPageRead:
    require_template_access(db, current_user.id, payload.template_id)
    return builder_layout_service.create_page(db, payload)


@router.get("/pages/{template_id}", response_model=list[BuilderPageRead])
def list_pages(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderPageRead]:
    require_template_access(db, current_user.id, template_id)
    return builder_layout_service.list_pages(db, template_id)


@router.post("/sections", response_model=BuilderSectionRead)
def create_section(payload: BuilderSectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderSectionRead:
    require_page_access(db, current_user.id, payload.page_id)
    return builder_layout_service.create_section(db, payload)


@router.get("/sections/{page_id}", response_model=list[BuilderSectionRead])
def list_sections(page_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderSectionRead]:
    require_page_access(db, current_user.id, page_id)
    return builder_layout_service.list_sections(db, page_id)


@router.post("/rows", response_model=BuilderRowRead)
def create_row(payload: BuilderRowCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderRowRead:
    require_section_access(db, current_user.id, payload.section_id)
    return builder_layout_service.create_row(db, payload)


@router.get("/rows/{section_id}", response_model=list[BuilderRowRead])
def list_rows(section_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderRowRead]:
    require_section_access(db, current_user.id, section_id)
    return builder_layout_service.list_rows(db, section_id)


@router.post("/columns", response_model=BuilderColumnRead)
def create_column(payload: BuilderColumnCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderColumnRead:
    require_row_access(db, current_user.id, payload.row_id)
    return builder_layout_service.create_column(db, payload)


@router.get("/columns/{row_id}", response_model=list[BuilderColumnRead])
def list_columns(row_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderColumnRead]:
    require_row_access(db, current_user.id, row_id)
    return builder_layout_service.list_columns(db, row_id)
