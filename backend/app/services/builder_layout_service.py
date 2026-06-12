from sqlalchemy.orm import Session

from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.schemas.builder_layout import BuilderColumnCreate, BuilderColumnRead, BuilderPageCreate, BuilderPageRead, BuilderRowCreate, BuilderRowRead, BuilderSectionCreate, BuilderSectionRead


def page_to_read(row: BuilderPage) -> BuilderPageRead:
    return BuilderPageRead(id=row.id, template_id=row.template_id, title=row.title, description=row.description, sort_order=row.sort_order, visible=row.visible == "true")


def section_to_read(row: BuilderSection) -> BuilderSectionRead:
    return BuilderSectionRead(id=row.id, page_id=row.page_id, title=row.title, description=row.description, collapsible=row.collapsible == "true", sort_order=row.sort_order, visible=row.visible == "true")


def row_to_read(row: BuilderRow) -> BuilderRowRead:
    return BuilderRowRead(id=row.id, section_id=row.section_id, sort_order=row.sort_order, responsive=row.responsive == "true")


def column_to_read(row: BuilderColumn) -> BuilderColumnRead:
    return BuilderColumnRead(id=row.id, row_id=row.row_id, desktop_width=row.desktop_width, tablet_width=row.tablet_width, mobile_width=row.mobile_width, sort_order=row.sort_order)


class BuilderLayoutService:
    def create_page(self, db: Session, payload: BuilderPageCreate) -> BuilderPageRead:
        row = BuilderPage(template_id=payload.template_id, title=payload.title, description=payload.description, sort_order=payload.sort_order, visible="true" if payload.visible else "false")
        db.add(row)
        db.commit()
        db.refresh(row)
        return page_to_read(row)

    def list_pages(self, db: Session, template_id: str) -> list[BuilderPageRead]:
        rows = db.query(BuilderPage).filter(BuilderPage.template_id == template_id).order_by(BuilderPage.sort_order).all()
        return [page_to_read(row) for row in rows]

    def create_section(self, db: Session, payload: BuilderSectionCreate) -> BuilderSectionRead:
        row = BuilderSection(page_id=payload.page_id, title=payload.title, description=payload.description, collapsible="true" if payload.collapsible else "false", sort_order=payload.sort_order, visible="true" if payload.visible else "false")
        db.add(row)
        db.commit()
        db.refresh(row)
        return section_to_read(row)

    def list_sections(self, db: Session, page_id: str) -> list[BuilderSectionRead]:
        rows = db.query(BuilderSection).filter(BuilderSection.page_id == page_id).order_by(BuilderSection.sort_order).all()
        return [section_to_read(row) for row in rows]

    def create_row(self, db: Session, payload: BuilderRowCreate) -> BuilderRowRead:
        row = BuilderRow(section_id=payload.section_id, sort_order=payload.sort_order, responsive="true" if payload.responsive else "false")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row_to_read(row)

    def list_rows(self, db: Session, section_id: str) -> list[BuilderRowRead]:
        rows = db.query(BuilderRow).filter(BuilderRow.section_id == section_id).order_by(BuilderRow.sort_order).all()
        return [row_to_read(row) for row in rows]

    def create_column(self, db: Session, payload: BuilderColumnCreate) -> BuilderColumnRead:
        row = BuilderColumn(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return column_to_read(row)

    def list_columns(self, db: Session, row_id: str) -> list[BuilderColumnRead]:
        rows = db.query(BuilderColumn).filter(BuilderColumn.row_id == row_id).order_by(BuilderColumn.sort_order).all()
        return [column_to_read(row) for row in rows]


builder_layout_service = BuilderLayoutService()
