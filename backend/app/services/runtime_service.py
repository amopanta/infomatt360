from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.schemas.runtime import RuntimeColumn, RuntimeComponent, RuntimePage, RuntimeRow, RuntimeSection, RuntimeTemplate


class RuntimeService:
    """Construye el JSON que consume el frontend runtime.

    Este servicio ensambla Template -> Pages -> Sections -> Rows -> Columns ->
    Components. El frontend no necesita conocer tablas internas del Builder.
    """

    def build_template_runtime(self, db: Session, template_id: str) -> RuntimeTemplate:
        template = db.query(BuilderTemplate).filter(BuilderTemplate.id == template_id).first()
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")

        pages = db.query(BuilderPage).filter(BuilderPage.template_id == template_id).order_by(BuilderPage.sort_order).all()
        runtime_pages: list[RuntimePage] = []

        for page in pages:
            sections = db.query(BuilderSection).filter(BuilderSection.page_id == page.id).order_by(BuilderSection.sort_order).all()
            runtime_sections: list[RuntimeSection] = []

            for section in sections:
                rows = db.query(BuilderRow).filter(BuilderRow.section_id == section.id).order_by(BuilderRow.sort_order).all()
                runtime_rows: list[RuntimeRow] = []

                for row in rows:
                    columns = db.query(BuilderColumn).filter(BuilderColumn.row_id == row.id).order_by(BuilderColumn.sort_order).all()
                    runtime_columns: list[RuntimeColumn] = []

                    for column in columns:
                        components = db.query(BuilderComponent).filter(
                            BuilderComponent.template_id == template_id,
                            BuilderComponent.column_id == column.id,
                        ).order_by(BuilderComponent.sort_order).all()

                        runtime_components = [
                            RuntimeComponent(
                                id=item.id,
                                type=item.component_type,
                                name=item.name,
                                label=item.label,
                                config_json=item.config_json,
                                rules_json=item.rules_json,
                            )
                            for item in components
                        ]

                        runtime_columns.append(
                            RuntimeColumn(
                                id=column.id,
                                desktop_width=column.desktop_width,
                                tablet_width=column.tablet_width,
                                mobile_width=column.mobile_width,
                                components=runtime_components,
                            )
                        )

                    runtime_rows.append(RuntimeRow(id=row.id, columns=runtime_columns))

                runtime_sections.append(
                    RuntimeSection(
                        id=section.id,
                        title=section.title,
                        description=section.description,
                        rows=runtime_rows,
                    )
                )

            runtime_pages.append(
                RuntimePage(
                    id=page.id,
                    title=page.title,
                    description=page.description,
                    sections=runtime_sections,
                )
            )

        return RuntimeTemplate(template_id=template.id, name=template.name, status=template.status, pages=runtime_pages)


runtime_service = RuntimeService()
