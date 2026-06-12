from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.builder_layout import BuilderColumnCreate, BuilderColumnRead, BuilderPageCreate, BuilderPageRead, BuilderRowCreate, BuilderRowRead, BuilderSectionCreate, BuilderSectionRead
from app.services.builder_layout_service import builder_layout_service

router = APIRouter()


@router.post("/pages", response_model=BuilderPageRead)
def create_page(payload: BuilderPageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderPageRead:
    return builder_layout_service.create_page(db, payload)


@router.get("/pages/{template_id}", response_model=list[BuilderPageRead])
def list_pages(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderPageRead]:
    return builder_layout_service.list_pages(db, template_id)


@router.post("/sections", response_model=BuilderSectionRead)
def create_section(payload: BuilderSectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderSectionRead:
    return builder_layout_service.create_section(db, payload)


@router.get("/sections/{page_id}", response_model=list[BuilderSectionRead])
def list_sections(page_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderSectionRead]:
    return builder_layout_service.list_sections(db, page_id)


@router.post("/rows", response_model=BuilderRowRead)
def create_row(payload: BuilderRowCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderRowRead:
    return builder_layout_service.create_row(db, payload)


@router.get("/rows/{section_id}", response_model=list[BuilderRowRead])
def list_rows(section_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderRowRead]:
    return builder_layout_service.list_rows(db, section_id)


@router.post("/columns", response_model=BuilderColumnRead)
def create_column(payload: BuilderColumnCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> BuilderColumnRead:
    return builder_layout_service.create_column(db, payload)


@router.get("/columns/{row_id}", response_model=list[BuilderColumnRead])
def list_columns(row_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BuilderColumnRead]:
    return builder_layout_service.list_columns(db, row_id)
