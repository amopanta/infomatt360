"""Exportador de plantillas Builder a XLSForm (.xlsx) -- la operacion
inversa de `xlsform_import_service.py`.

Reutiliza `runtime_service.build_template_runtime()` para obtener el arbol
completo (paginas -> secciones -> filas -> columnas -> componentes) sin
volver a recorrer los modelos de Builder desde cero, y lo aplana en una
sola hoja `survey` -- la estructura de paginas/secciones no tiene un
equivalente directo en XLSForm, igual que el importador tampoco recrea
paginas/secciones multiples a partir del archivo.

Ademas de `type`/`name`/`label` escribe las columnas reales del estandar
(`hint`, `required`, `relevant`, `constraint`, `constraint_message`,
`appearance`, `parameters`), sintetizandolas desde las mismas claves de
config_json que ya usa el constructor visual (`placeholder`, `required`,
`relevant`, `pattern`/`min`/`max`/`min_length`/`max_length`). Cuando el campo
vino de una importacion previa, se preserva el texto original de
`relevant`/`constraint` (guardado en `relevant_expression`/
`constraint_expression`) para garantizar un round-trip fiel incluso en
expresiones que el importador no supo traducir a validaciones nativas --
ver `docs/93_EXPORTADOR_XLSFORM.md`.

No es un exportador a XForm (XML): InfoMatt360 nunca compila a XForm
porque el Runtime consume su propio JSON, no XForm (ver docs/93).
"""

import json
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.field_types import FIELD_TYPES
from app.schemas.runtime import RuntimeComponent
from app.services.runtime_service import runtime_service

# Tipo interno -> tipo XLSForm/ODK. SELECT/MULTISELECT/DROPDOWN/RANKING,
# BOOLEAN, LIKERT_5/7 y REPEAT tienen logica especial (generan hoja
# `choices` o se desenrollan) y se resuelven en `_write_field`, no aqui.
# Cualquier tipo nuevo que se agregue a `app.core.field_types` sin
# actualizar este mapa cae en el fallback "text" (`.get(..., "text")`),
# nunca revienta la exportacion.
EXPORT_TYPE_MAP: dict[str, str] = {
    "TEXT": "text", "TEXTAREA": "text", "DOCUMENT_ID": "text",
    "NUMBER": "integer", "INTEGER": "integer", "DECIMAL": "decimal",
    "EMAIL": "text", "PHONE": "text", "URL": "text",
    "DATE": "date", "TIME": "time", "DATETIME": "dateTime",
    "YEAR": "integer", "MONTH": "text", "WEEK": "text",
    "PERCENTAGE": "decimal", "CURRENCY": "decimal",
    "IMAGE": "image", "FILE": "file", "PDF": "file", "MULTIFILE": "file",
    "AUDIO": "audio", "VIDEO": "video", "SIGNATURE": "image",
    "GPS": "geopoint", "GEOTRACE": "geotrace", "GEOSHAPE": "geoshape",
    "MATRIX": "text",
    "CALCULATE": "calculate", "REFERENCE": "text", "PARENT_CHILD": "text", "LOOKUP": "text",
    "HIDDEN": "hidden",
    "UUID": "calculate", "RESPONSE_ID": "calculate", "INTERVIEW_DURATION": "calculate",
    "CAPTURED_BY": "text", "CHANGE_HISTORY": "text",
    "BARCODE": "barcode", "QR": "barcode", "OCR": "image",
    "NPS": "integer", "RATING": "text",
    "RANGE": "range",
}

YES_NO_LIST = "yes_no"
SURVEY_HEADER = ["type", "name", "label", "hint", "required", "relevant", "constraint", "constraint_message", "appearance", "parameters"]
CHOICES_HEADER = ["list_name", "name", "label"]

# Un ejemplo por cada tipo del catalogo interno (`app.core.field_types`),
# para la plantilla maestra descargable (ver docs/93). Se mantiene como una
# lista de tuplas (tipo, nombre, etiqueta, config) -- el mismo formato que
# consume `_build_workbook` para las plantillas reales -- y no como
# componentes de Builder, porque no pertenece a ningun proyecto/plantilla
# real: es solo material de referencia para descargar y editar en Excel.
MASTER_TEMPLATE_FIELDS: list[tuple[str, str, str, dict]] = [
    ("TEXT", "texto_ejemplo", "Texto libre", {"placeholder": "Ejemplo: nombre completo", "required": True}),
    ("TEXTAREA", "texto_largo_ejemplo", "Texto largo", {"placeholder": "Parrafos o comentarios extensos"}),
    ("DOCUMENT_ID", "documento_ejemplo", "Numero de documento", {"placeholder": "Cedula o identificacion", "required": True}),
    ("NUMBER", "numero_ejemplo", "Numero", {}),
    ("INTEGER", "entero_ejemplo", "Cantidad de integrantes", {"min": 0, "max": 20, "required": True}),
    ("DECIMAL", "decimal_ejemplo", "Peso, area o valor con decimales", {}),
    ("EMAIL", "correo_ejemplo", "Correo electronico", {}),
    ("PHONE", "telefono_ejemplo", "Telefono", {}),
    ("URL", "url_ejemplo", "Enlace web", {}),
    ("BOOLEAN", "acepta_terminos_ejemplo", "Acepta los terminos", {"required": True}),
    ("BOOLEAN", "consentimiento_ejemplo", "Consentimiento de tratamiento de datos (estilo LimeSurvey)", {"required": True, "appearance": "consent"}),
    ("TEXT", "comentario_condicional_ejemplo", "Comentario adicional (solo si acepta terminos)", {"relevant": {"field": "acepta_terminos_ejemplo", "operator": "equals", "value": "1"}}),
    ("SELECT", "seleccion_unica_ejemplo", "Seleccion unica", {"options": [{"value": "opcion_a", "label": "Opcion A"}, {"value": "opcion_b", "label": "Opcion B"}, {"value": "opcion_c", "label": "Opcion C"}]}),
    ("SELECT", "seleccion_horizontal_ejemplo", "Seleccion unica horizontal (estilo LimeSurvey)", {"appearance": "horizontal", "options": [{"value": "opcion_a", "label": "Opcion A"}, {"value": "opcion_b", "label": "Opcion B"}]}),
    ("MULTISELECT", "seleccion_multiple_ejemplo", "Seleccion multiple", {"options": [{"value": "alternativa_1", "label": "Alternativa 1"}, {"value": "alternativa_2", "label": "Alternativa 2"}]}),
    ("DROPDOWN", "lista_desplegable_ejemplo", "Lista desplegable", {"options": [{"value": "co", "label": "Colombia"}, {"value": "mx", "label": "Mexico"}, {"value": "pe", "label": "Peru"}]}),
    ("DATE", "fecha_ejemplo", "Fecha", {}),
    ("TIME", "hora_ejemplo", "Hora", {}),
    ("DATETIME", "fecha_hora_ejemplo", "Fecha y hora", {}),
    ("YEAR", "anio_ejemplo", "Anio", {}),
    ("MONTH", "mes_ejemplo", "Mes", {}),
    ("WEEK", "semana_ejemplo", "Semana", {}),
    ("PERCENTAGE", "porcentaje_ejemplo", "Porcentaje", {}),
    ("CURRENCY", "moneda_ejemplo", "Valor monetario", {}),
    ("IMAGE", "imagen_ejemplo", "Fotografia", {}),
    ("FILE", "archivo_ejemplo", "Archivo adjunto (PDF, DOCX, etc.)", {}),
    ("PDF", "pdf_ejemplo", "Documento PDF", {}),
    ("MULTIFILE", "archivos_multiples_ejemplo", "Varios archivos", {}),
    ("AUDIO", "audio_ejemplo", "Nota de audio", {}),
    ("VIDEO", "video_ejemplo", "Video", {}),
    ("SIGNATURE", "firma_ejemplo", "Firma", {}),
    ("GPS", "gps_ejemplo", "Ubicacion GPS (punto)", {}),
    ("GEOTRACE", "recorrido_ejemplo", "Recorrido GPS (linea)", {}),
    ("GEOSHAPE", "poligono_ejemplo", "Area GPS (poligono)", {}),
    ("MATRIX", "matriz_ejemplo", "Matriz", {}),
    ("LIKERT_5", "likert5_ejemplo", "Escala de 1 a 5", {}),
    ("LIKERT_7", "likert7_ejemplo", "Escala de 1 a 7", {}),
    ("RANGE", "rango_ejemplo", "Deslizador (0-100)", {"min": 0, "max": 100, "step": 5}),
    ("RANKING", "ranking_ejemplo", "Ordene sus prioridades", {"options": [{"value": "prioridad_a", "label": "Prioridad A"}, {"value": "prioridad_b", "label": "Prioridad B"}, {"value": "prioridad_c", "label": "Prioridad C"}]}),
    ("NPS", "nps_ejemplo", "Recomendacion del 0 al 10", {}),
    ("RATING", "calificacion_ejemplo", "Calificacion", {}),
    ("CALCULATE", "calculo_ejemplo", "Calculo automatico", {}),
    ("REFERENCE", "referencia_ejemplo", "Referencia a otro formulario", {}),
    ("PARENT_CHILD", "padre_hijo_ejemplo", "Relacion padre-hijo", {}),
    ("LOOKUP", "consulta_ejemplo", "Consulta de catalogo", {}),
    ("HIDDEN", "oculto_ejemplo", "Campo oculto", {}),
    ("UUID", "uuid_ejemplo", "Identificador unico", {}),
    ("RESPONSE_ID", "id_respuesta_ejemplo", "ID de la respuesta", {}),
    ("INTERVIEW_DURATION", "duracion_entrevista_ejemplo", "Duracion de la entrevista", {}),
    ("CAPTURED_BY", "capturado_por_ejemplo", "Usuario que capturo", {}),
    ("CHANGE_HISTORY", "historial_cambios_ejemplo", "Historial de cambios", {}),
    ("BARCODE", "codigo_barras_ejemplo", "Codigo de barras", {}),
    ("QR", "qr_ejemplo", "Codigo QR", {}),
    ("OCR", "ocr_ejemplo", "Imagen con OCR", {}),
    ("REPEAT", "integrantes_hogar_ejemplo", "Integrantes del hogar (repetible)", {"fields": [
        {"name": "nombre_integrante_ejemplo", "label": "Nombre", "component_type": "TEXT", "config": {}},
        {"name": "edad_integrante_ejemplo", "label": "Edad", "component_type": "INTEGER", "config": {}},
    ]}),
]


def _parse_config(config_json: str | None) -> dict:
    if not config_json:
        return {}
    try:
        parsed = json.loads(config_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _format_number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _synthesize_relevant(config: dict) -> str:
    if config.get("relevant_expression"):
        return str(config["relevant_expression"])
    relevant = config.get("relevant")
    if not isinstance(relevant, dict) or not relevant.get("field"):
        return ""
    field = relevant["field"]
    operator = relevant.get("operator", "equals")
    value = relevant.get("value", "")
    if operator == "not_empty":
        return f"${{{field}}} != ''"
    if operator == "empty":
        return f"${{{field}}} = ''"
    if operator == "not_equals":
        return f"${{{field}}} != '{value}'"
    return f"${{{field}}} = '{value}'"


def _synthesize_constraint(config: dict, comp_type: str) -> str:
    if config.get("constraint_expression"):
        return str(config["constraint_expression"])
    parts: list[str] = []
    if config.get("pattern"):
        parts.append(f"regex(., '{config['pattern']}')")
    # min/max de un RANGE son los limites del deslizador (van en `parameters`),
    # no una validacion de rango sobre la respuesta.
    if comp_type != "RANGE":
        if config.get("min") is not None:
            parts.append(f". >= {_format_number(config['min'])}")
        if config.get("max") is not None:
            parts.append(f". <= {_format_number(config['max'])}")
    if config.get("min_length") is not None:
        parts.append(f"string-length(.) >= {config['min_length']}")
    if config.get("max_length") is not None:
        parts.append(f"string-length(.) <= {config['max_length']}")
    return " and ".join(parts)


def _synthesize_parameters(comp_type: str, config: dict) -> str:
    if comp_type == "RANGE":
        start = _format_number(config.get("min", 0))
        end = _format_number(config.get("max", 100))
        step = _format_number(config.get("step", 1))
        return f"start={start} end={end} step={step}"
    parameters = config.get("parameters")
    return str(parameters) if parameters else ""


def _build_row(xlsform_type: str, name: str, label: str, config: dict, comp_type: str) -> list[str]:
    return [
        xlsform_type, name, label,
        str(config.get("placeholder") or ""),
        "yes" if config.get("required") else "",
        _synthesize_relevant(config),
        _synthesize_constraint(config, comp_type),
        str(config.get("constraint_message") or ""),
        str(config.get("appearance") or ""),
        _synthesize_parameters(comp_type, config),
    ]


class XlsformExportService:
    def export_xlsform(self, db: Session, template_id: str) -> bytes:
        template = runtime_service.build_template_runtime(db, template_id)

        field_specs: list[tuple[str, str, str, dict]] = []

        def collect_component(component: RuntimeComponent) -> None:
            field_specs.append((component.type, component.name, component.label, _parse_config(component.config_json)))

        for page in template.pages:
            for section in page.sections:
                for row in section.rows:
                    for column in row.columns:
                        for component in column.components:
                            collect_component(component)

        return self._save(self._build_workbook(field_specs))

    def build_master_template(self) -> bytes:
        return self._save(self._build_workbook(MASTER_TEMPLATE_FIELDS))

    def _save(self, workbook: Workbook) -> bytes:
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def _build_workbook(self, field_specs: list[tuple[str, str, str, dict]]) -> Workbook:
        workbook = Workbook()
        survey_sheet = workbook.active
        survey_sheet.title = "survey"
        survey_sheet.append(SURVEY_HEADER)
        choices_sheet = workbook.create_sheet("choices")
        choices_sheet.append(CHOICES_HEADER)
        seen_lists: set[str] = set()

        def add_choices(list_name: str, options: list[dict]) -> None:
            if list_name in seen_lists:
                return
            seen_lists.add(list_name)
            for option in options:
                choices_sheet.append([list_name, str(option.get("value", "")), str(option.get("label", option.get("value", "")))])

        def write_field(comp_type: str, name: str, label: str, config: dict) -> None:
            comp_type = comp_type.upper()

            if comp_type in ("SELECT", "MULTISELECT", "DROPDOWN", "RANKING"):
                add_choices(name, config.get("options", []))
                prefix = "select_multiple" if comp_type == "MULTISELECT" else "rank" if comp_type == "RANKING" else "select_one"
                survey_sheet.append(_build_row(f"{prefix} {name}", name, label, config, comp_type))
                return

            if comp_type == "BOOLEAN":
                add_choices(YES_NO_LIST, [{"value": "1", "label": "Sí"}, {"value": "0", "label": "No"}])
                survey_sheet.append(_build_row(f"select_one {YES_NO_LIST}", name, label, config, comp_type))
                return

            if comp_type in ("LIKERT_5", "LIKERT_7"):
                scale = 5 if comp_type == "LIKERT_5" else 7
                add_choices(name, [{"value": str(i), "label": str(i)} for i in range(1, scale + 1)])
                survey_sheet.append(_build_row(f"select_one {name}", name, label, config, comp_type))
                return

            if comp_type == "REPEAT":
                survey_sheet.append(["begin_repeat", name, label, "", "", "", "", "", "", ""])
                for nested in config.get("fields") or []:
                    nested_type = str(nested.get("component_type", "TEXT"))
                    nested_name = str(nested.get("name", ""))
                    nested_label = str(nested.get("label", nested_name))
                    write_field(nested_type, nested_name, nested_label, nested.get("config") or {})
                survey_sheet.append(["end_repeat", "", "", "", "", "", "", "", "", ""])
                return

            survey_sheet.append(_build_row(EXPORT_TYPE_MAP.get(comp_type, "text"), name, label, config, comp_type))

        for comp_type, name, label, config in field_specs:
            write_field(comp_type, name, label, config)

        return workbook


assert {field[0] for field in MASTER_TEMPLATE_FIELDS} == set(FIELD_TYPES), "MASTER_TEMPLATE_FIELDS debe cubrir todos los tipos de app.core.field_types"

xlsform_export_service = XlsformExportService()
