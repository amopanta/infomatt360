"""Utilidades compartidas entre los importadores de formularios (XLSForm,
SurveyMonkey, LimeSurvey):

- `create_field_component`: crea una fila -> columna -> componente de Builder
  para un campo ya resuelto a un tipo interno. Antes vivia como metodo privado
  de `XlsformImportService`; se extrajo para que los nuevos importadores no
  dupliquen la misma secuencia de 3 llamadas.
- `prepare_target_template`: decide si el importador debe crear una plantilla
  nueva (comportamiento de siempre) o **reemplazar en el mismo lugar** una
  plantilla existente (mismo `template_id`, como el "redeploy" de
  KoboToolbox) -- ver `docs/95_REEMPLAZO_DE_PLANTILLA_EN_EL_MISMO_LUGAR.md`.
"""

import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate, BuilderVersion
from app.models.builder_layout import BuilderColumn, BuilderPage, BuilderRow, BuilderSection
from app.schemas.builder import BuilderComponentCreate, BuilderTemplateCreate
from app.schemas.builder_layout import BuilderColumnCreate, BuilderRowCreate
from app.services.builder_layout_service import builder_layout_service
from app.services.builder_service import builder_service


def create_field_component(
    db: Session, template_id: str, section_id: str, sort_order: int, *,
    component_type: str, name: str, label: str, config: dict | None,
) -> None:
    row = builder_layout_service.create_row(db, BuilderRowCreate(section_id=section_id, sort_order=sort_order))
    column = builder_layout_service.create_column(db, BuilderColumnCreate(row_id=row.id, desktop_width=12, tablet_width=12, mobile_width=12, sort_order=0))
    builder_service.add_component(db, BuilderComponentCreate(
        template_id=template_id,
        column_id=column.id,
        component_type=component_type,
        name=name,
        label=label,
        config_json=json.dumps(config) if config is not None else None,
        sort_order=sort_order,
    ))


def _next_version_number(db: Session, template_id: str) -> int:
    last = (
        db.query(BuilderVersion)
        .filter(BuilderVersion.template_id == template_id)
        .order_by(BuilderVersion.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


def _snapshot_template_version(db: Session, template_id: str) -> None:
    """Guarda la estructura actual (antes de sobrescribirla) como una
    `BuilderVersion` archivada -- es el respaldo que permite deshacer un
    reemplazo, ya que antes de este cambio el modelo se guardaba pero nunca
    se leia para nada."""
    from app.services.runtime_service import runtime_service

    runtime_tree = runtime_service.build_template_runtime(db, template_id)
    version = BuilderVersion(
        template_id=template_id,
        version_number=_next_version_number(db, template_id),
        schema_json=runtime_tree.model_dump_json(),
        status="archived",
    )
    db.add(version)
    db.commit()


def _wipe_template_layout(db: Session, template_id: str) -> None:
    """Borra paginas/secciones/filas/columnas/componentes de una plantilla,
    dejando la fila de `BuilderTemplate` intacta (mismo id, mismo nombre,
    mismo tema visual) para que el reemplazo ocurra en el mismo lugar."""
    db.query(BuilderComponent).filter(BuilderComponent.template_id == template_id).delete()
    pages = db.query(BuilderPage).filter(BuilderPage.template_id == template_id).all()
    for page in pages:
        sections = db.query(BuilderSection).filter(BuilderSection.page_id == page.id).all()
        for section in sections:
            rows = db.query(BuilderRow).filter(BuilderRow.section_id == section.id).all()
            for row in rows:
                db.query(BuilderColumn).filter(BuilderColumn.row_id == row.id).delete()
            db.query(BuilderRow).filter(BuilderRow.section_id == section.id).delete()
        db.query(BuilderSection).filter(BuilderSection.page_id == page.id).delete()
    db.query(BuilderPage).filter(BuilderPage.template_id == template_id).delete()
    db.commit()


def prepare_target_template(db: Session, project_id: str, filename: str, replace_template_id: str | None) -> tuple[str, bool]:
    """Punto de entrada unico para los 3 importadores: decide si crean una
    plantilla nueva o reemplazan una existente en el mismo lugar.

    Devuelve `(template_id, is_replace)`. Si `replace_template_id` viene
    dado, se verifica que exista y pertenezca al proyecto (nunca se
    reemplaza una plantilla de otro proyecto solo porque alguien adivine su
    id), se guarda un respaldo de la estructura actual en `BuilderVersion`,
    se borra su contenido visual, y el importador vuelve a poblarlo bajo el
    mismo `template_id` -- los registros ya capturados siguen ligados a ese
    mismo id (no se pierden ni se re-etiquetan)."""
    if replace_template_id:
        template = (
            db.query(BuilderTemplate)
            .filter(BuilderTemplate.id == replace_template_id, BuilderTemplate.project_id == project_id)
            .first()
        )
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La plantilla a reemplazar no existe o no pertenece a este proyecto")
        _snapshot_template_version(db, template.id)
        _wipe_template_layout(db, template.id)
        return template.id, True

    template = builder_service.create_template(db, BuilderTemplateCreate(project_id=project_id, name=filename.rsplit(".", 1)[0], status="draft"))
    return template.id, False
