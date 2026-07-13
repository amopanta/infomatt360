"""Utilidad compartida entre los importadores de formularios (XLSForm,
SurveyMonkey, LimeSurvey): crea una fila -> columna -> componente de Builder
para un campo ya resuelto a un tipo interno. Antes vivia como metodo privado
de `XlsformImportService`; se extrajo para que los nuevos importadores no
dupliquen la misma secuencia de 3 llamadas.
"""

import json

from sqlalchemy.orm import Session

from app.schemas.builder import BuilderComponentCreate
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
