"""Importador de plantillas XLSForm (estandar ODK/KoboToolbox).

Lee las hojas `survey` y `choices` de un archivo .xlsx y crea una plantilla
Builder equivalente, reutilizando el catalogo de tipos ya existente
(`app.core.field_types`), que ya conoce los alias de ODK (`select_one`,
`select_multiple`, `geopoint`, `begin_repeat`, etc.).

No requiere generar codigo nuevo de mapeo de tipos para la mayoria de casos:
`normalize_field_type()` ya acepta nombres XLSForm en minuscula porque los
convierte a mayuscula antes de comparar contra el catalogo. Solo se resuelven
aqui las particularidades propias del formato de archivo: `select_one <lista>`
con el nombre de lista embebido, grupos (`begin_group`/`end_group`, que se
aplanan) y repeticiones (`begin_repeat`/`end_repeat`, que se agrupan en un
solo componente REPEAT con los campos anidados en `config_json`).
"""

import json
from io import BytesIO

from fastapi import HTTPException, status
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.field_types import normalize_field_type
from app.schemas.builder import BuilderComponentCreate, BuilderTemplateCreate
from app.schemas.builder_layout import BuilderColumnCreate, BuilderPageCreate, BuilderRowCreate, BuilderSectionCreate
from app.schemas.xlsform import XlsformImportResult
from app.services.builder_layout_service import builder_layout_service
from app.services.builder_service import builder_service

# Filas de metadatos propios de ODK/KoboToolbox sin equivalente de campo
# visible: se omiten en vez de forzar un mapeo artificial.
SKIP_TYPES = {
    "note", "start", "end", "today", "deviceid", "subscriberid", "simserial",
    "username", "audit", "text-audit", "calculate_here",
}
GROUP_OPEN_TYPES = {"begin_group", "begin group", "begin_repeat", "begin repeat"}
GROUP_CLOSE_TYPES = {"end_group", "end group", "end_repeat", "end repeat"}


def _normalize_header(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def _find_column(headers: list[str], *candidates: str) -> int | None:
    normalized_candidates = [candidate.replace(" ", "_") for candidate in candidates]
    for index, header in enumerate(headers):
        if header.replace(" ", "_") in normalized_candidates:
            return index
    for index, header in enumerate(headers):
        if any(header.startswith(candidate) for candidate in normalized_candidates):
            return index
    return None


def _read_sheet_rows(workbook, sheet_name: str) -> tuple[list[str], list[list[object]]]:
    if sheet_name not in workbook.sheetnames:
        return [], []
    sheet = workbook[sheet_name]
    rows_iter = sheet.iter_rows(values_only=True)
    headers = [_normalize_header(cell) for cell in next(rows_iter, [])]
    rows = [list(row) for row in rows_iter if row and any(cell is not None for cell in row)]
    return headers, rows


def _cell(row: list[object], index: int | None) -> str:
    if index is None or index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


class XlsformImportService:
    def import_xlsform(self, db: Session, project_id: str, filename: str, content: bytes, user_id: str | None) -> XlsformImportResult:
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"No fue posible leer el archivo XLSForm: {exc}") from exc

        survey_headers, survey_rows = _read_sheet_rows(workbook, "survey")
        if not survey_rows:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El archivo no tiene una hoja 'survey' con filas de preguntas")
        choices_headers, choices_rows = _read_sheet_rows(workbook, "choices")

        type_col = _find_column(survey_headers, "type")
        name_col = _find_column(survey_headers, "name")
        label_col = _find_column(survey_headers, "label")
        if type_col is None or name_col is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La hoja 'survey' debe tener columnas 'type' y 'name'")

        list_col = _find_column(choices_headers, "list_name")
        choice_name_col = _find_column(choices_headers, "name")
        choice_label_col = _find_column(choices_headers, "label")
        choices_by_list: dict[str, list[dict[str, str]]] = {}
        for row in choices_rows:
            list_name = _cell(row, list_col)
            if not list_name:
                continue
            choices_by_list.setdefault(list_name, []).append({
                "value": _cell(row, choice_name_col),
                "label": _cell(row, choice_label_col) or _cell(row, choice_name_col),
            })

        template = builder_service.create_template(db, BuilderTemplateCreate(project_id=project_id, name=filename.rsplit(".", 1)[0], status="draft"))
        page = builder_layout_service.create_page(db, BuilderPageCreate(template_id=template.id, title="Importado de XLSForm", sort_order=0))
        section = builder_layout_service.create_section(db, BuilderSectionCreate(page_id=page.id, title="Preguntas", sort_order=0))

        warnings: list[str] = []
        imported_fields = 0
        sort_order = 0
        repeat_stack: list[dict[str, object]] = []

        for row in survey_rows:
            raw_type = _cell(row, type_col)
            if not raw_type:
                continue
            parts = raw_type.split()
            base_type = parts[0].lower()
            field_name = _cell(row, name_col)
            field_label = _cell(row, label_col) or field_name

            if base_type in ("begin_group", "begin group"):
                continue
            if base_type in ("end_group", "end group"):
                continue
            if base_type in ("begin_repeat", "begin repeat"):
                repeat_stack.append({"name": field_name, "label": field_label, "fields": []})
                continue
            if base_type in ("end_repeat", "end repeat"):
                if not repeat_stack:
                    warnings.append(f"'end_repeat' sin 'begin_repeat' correspondiente (fila con name={field_name!r})")
                    continue
                repeat = repeat_stack.pop()
                config = {"fields": repeat["fields"]}
                self._create_field_component(
                    db, template.id, section.id, sort_order,
                    component_type="REPEAT", name=str(repeat["name"]) or f"repeat_{sort_order}",
                    label=str(repeat["label"]) or "Repetible", config=config,
                )
                sort_order += 1
                imported_fields += 1
                continue
            if base_type in SKIP_TYPES:
                continue
            if not field_name:
                warnings.append(f"Fila con tipo '{raw_type}' sin columna 'name'; se omitio")
                continue

            mapped_type, config, warning = self._resolve_type(base_type, parts, choices_by_list)
            if warning:
                warnings.append(f"Campo '{field_name}': {warning}")

            if repeat_stack:
                repeat_stack[-1]["fields"].append({"name": field_name, "label": field_label, "component_type": mapped_type, "config": config})
                continue

            self._create_field_component(db, template.id, section.id, sort_order, component_type=mapped_type, name=field_name, label=field_label, config=config)
            sort_order += 1
            imported_fields += 1

        if repeat_stack:
            warnings.append("El archivo termino con un 'begin_repeat' sin cerrar; los campos restantes se descartaron")

        return XlsformImportResult(template_id=template.id, imported_fields=imported_fields, warnings=warnings)

    def _resolve_type(self, base_type: str, parts: list[str], choices_by_list: dict[str, list[dict[str, str]]]) -> tuple[str, dict | None, str | None]:
        if base_type in ("select_one", "select_multiple", "select_one_from_file"):
            list_name = parts[1] if len(parts) > 1 else ""
            options = choices_by_list.get(list_name, [])
            config = {"options": options}
            mapped = "MULTISELECT" if base_type == "select_multiple" else "SELECT"
            warning = None if options or not list_name else f"lista de opciones '{list_name}' no encontrada en la hoja choices"
            return mapped, config, warning
        try:
            return normalize_field_type(base_type), None, None
        except ValueError:
            return "HIDDEN", None, f"tipo '{base_type}' no tiene equivalente directo; se importo como campo oculto"

    def _create_field_component(self, db: Session, template_id: str, section_id: str, sort_order: int, *, component_type: str, name: str, label: str, config: dict | None) -> None:
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


xlsform_import_service = XlsformImportService()
