"""Read-only XLSForm validation and replacement diff."""

import hashlib
import json
from io import BytesIO

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate
from app.schemas.xlsform import FormFieldChange, XlsformPreview
from app.services.runtime_service import runtime_service
from app.services.xlsform_import_service import _cell, _find_column, _read_sheet_rows, xlsform_import_service


COMPARE_KEYS = [
    ("options", "lista de opciones"), ("required", "obligatoriedad"),
    ("required_message", "mensaje obligatorio"), ("relevant_expression", "regla relevant"),
    ("constraint_expression", "restricción"), ("constraint_message", "mensaje de restricción"),
    ("calculation", "cálculo"), ("choice_filter", "filtro de opciones"),
    ("default", "valor predeterminado"), ("appearance", "apariencia"),
    ("placeholder", "ayuda"),
]


def template_fingerprint(db: Session, template_id: str) -> str:
    snapshot = runtime_service.build_template_runtime(db, template_id)
    return hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()


def preview_xlsform(db: Session, project_id: str, filename: str, content: bytes, replace_template_id: str | None) -> XlsformPreview:
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el XLSForm: {exc}") from exc
    headers, rows = _read_sheet_rows(workbook, "survey")
    if not rows or _find_column(headers, "type") is None or _find_column(headers, "name") is None:
        raise HTTPException(status_code=422, detail="La hoja survey necesita type, name y preguntas")
    choice_headers, choice_rows = _read_sheet_rows(workbook, "choices")
    choices: dict[str, list[dict[str, str]]] = {}
    for row in choice_rows:
        list_name = _cell(row, _find_column(choice_headers, "list_name"))
        if not list_name:
            continue
        option = {"value": _cell(row, _find_column(choice_headers, "name")), "label": _cell(row, _find_column(choice_headers, "label"))}
        for index, header in enumerate(choice_headers):
            if header and header not in {"list_name", "name", "label"}:
                option[header] = _cell(row, index)
        choices.setdefault(list_name, []).append(option)
    result = XlsformPreview(format="xlsform", filename=filename, file_sha256=hashlib.sha256(content).hexdigest())
    incoming: dict[str, dict] = {}
    structure: list[str] = []
    for number, row in enumerate(rows, 2):
        raw_type = _cell(row, _find_column(headers, "type"))
        name = _cell(row, _find_column(headers, "name"))
        if not raw_type:
            continue
        parts = raw_type.split()
        base = parts[0].lower()
        if base in {"begin_group", "begin_repeat"}:
            structure.append(base)
            continue
        if base in {"end_group", "end_repeat"}:
            expected = base.replace("end", "begin", 1)
            if not structure or structure[-1] != expected:
                result.errors.append(f"Fila {number}: cierre {base} sin apertura correspondiente")
            else:
                structure.pop()
            continue
        if base in {"note", "start", "end", "today", "deviceid", "subscriberid", "simserial", "username", "audit", "text-audit", "calculate_here", "background-audio"}:
            continue
        if not name:
            result.errors.append(f"Fila {number}: pregunta sin name")
            continue
        if name in incoming:
            result.errors.append(f"Fila {number}: name duplicado «{name}»")
            continue
        mapped, config, warning = xlsform_import_service._resolve_type(base, parts, choices)
        if warning:
            (result.errors if (mapped == "HIDDEN" and replace_template_id) or "no encontrada" in warning else result.warnings).append(f"Fila {number}, {name}: {warning}")
        config, warnings = xlsform_import_service._apply_common_columns(
            config, mapped,
            hint=_cell(row, _find_column(headers, "hint")),
            required=_cell(row, _find_column(headers, "required")),
            required_message=_cell(row, _find_column(headers, "required_message")),
            relevant=_cell(row, _find_column(headers, "relevant")),
            constraint=_cell(row, _find_column(headers, "constraint")),
            constraint_message=_cell(row, _find_column(headers, "constraint_message")),
            appearance=_cell(row, _find_column(headers, "appearance")),
            parameters=_cell(row, _find_column(headers, "parameters")),
            calculation=_cell(row, _find_column(headers, "calculation")),
            choice_filter=_cell(row, _find_column(headers, "choice_filter")),
            default=_cell(row, _find_column(headers, "default")),
        )
        result.warnings.extend(f"Fila {number}, {name}: {warning}" for warning in warnings)
        incoming[name] = {"type": mapped, "label": _cell(row, _find_column(headers, "label")) or name, "config": config or {}}
    if structure:
        result.errors.append(f"Hay {len(structure)} grupo(s) o repetición(es) sin cerrar")
    if not incoming:
        result.errors.append("No hay preguntas importables")
    previous: dict[str, dict] = {}
    if replace_template_id:
        template = db.query(BuilderTemplate).filter(BuilderTemplate.id == replace_template_id, BuilderTemplate.project_id == project_id).first()
        if template is None:
            raise HTTPException(status_code=404, detail="Formulario a reemplazar no encontrado")
        result.target_sha256 = template_fingerprint(db, replace_template_id)
        components = db.query(BuilderComponent).filter(BuilderComponent.template_id == replace_template_id).all()
        for component in components:
            try:
                config = json.loads(component.config_json) if component.config_json else {}
            except ValueError:
                config = {}
            previous[component.name] = {"type": component.component_type, "label": component.label, "config": config}
    result.added = sorted(incoming.keys() - previous.keys())
    result.removed = sorted(previous.keys() - incoming.keys())
    for name in sorted(incoming.keys() & previous.keys()):
        new, old = incoming[name], previous[name]
        changes = []
        if new["type"] != old["type"]:
            changes.append("tipo")
        if new["label"] != old["label"]:
            changes.append("etiqueta")
        for key, label in COMPARE_KEYS:
            if new["config"].get(key) != old["config"].get(key):
                changes.append(label)
        if changes:
            result.modified.append(FormFieldChange(name=name, changes=changes))
    return result
