"""Autorizacion compartida para la jerarquia del Builder."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.builder import BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.services.assignment_service import assignment_service


def require_template_access(db: Session, user_id: str, template_id: str) -> BuilderTemplate:
    template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
    if not assignment_service.user_has_project_access(db, user_id, template.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al proyecto")
    return template


def require_page_access(db: Session, user_id: str, page_id: str) -> BuilderPage:
    page = db.query(BuilderPage).filter(BuilderPage.id == page_id).first()
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pagina no encontrada")
    require_template_access(db, user_id, page.template_id)
    return page


def require_section_access(db: Session, user_id: str, section_id: str) -> BuilderSection:
    section = db.query(BuilderSection).filter(BuilderSection.id == section_id).first()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seccion no encontrada")
    require_page_access(db, user_id, section.page_id)
    return section


def require_row_access(db: Session, user_id: str, row_id: str) -> BuilderRow:
    row = db.query(BuilderRow).filter(BuilderRow.id == row_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fila no encontrada")
    require_section_access(db, user_id, row.section_id)
    return row


def require_column_access(db: Session, user_id: str, column_id: str) -> BuilderColumn:
    column = db.query(BuilderColumn).filter(BuilderColumn.id == column_id).first()
    if column is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Columna no encontrada")
    require_row_access(db, user_id, column.row_id)
    return column


def template_id_for_column(db: Session, column: BuilderColumn) -> str:
    row = db.query(BuilderRow).filter(BuilderRow.id == column.row_id).one()
    section = db.query(BuilderSection).filter(BuilderSection.id == row.section_id).one()
    page = db.query(BuilderPage).filter(BuilderPage.id == section.page_id).one()
    return page.template_id
