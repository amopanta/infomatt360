"""Catalogo canonico de tipos de campo admitidos por Builder y Compiler."""

FIELD_TYPES = frozenset(
    {
        "TEXT", "TEXTAREA", "DOCUMENT_ID", "NUMBER", "INTEGER", "DECIMAL",
        "EMAIL", "PHONE", "URL",
        "BOOLEAN", "SELECT", "MULTISELECT", "DROPDOWN",
        "DATE", "TIME", "DATETIME", "YEAR", "MONTH", "WEEK",
        "PERCENTAGE", "CURRENCY",
        "IMAGE", "FILE", "PDF", "MULTIFILE", "AUDIO", "VIDEO", "SIGNATURE",
        "GPS", "GEOTRACE", "GEOSHAPE",
        "REPEAT", "MATRIX", "LIKERT_5", "LIKERT_7",
        "CALCULATE", "REFERENCE", "PARENT_CHILD", "LOOKUP", "HIDDEN",
        "UUID", "RESPONSE_ID", "INTERVIEW_DURATION", "CAPTURED_BY", "CHANGE_HISTORY",
        "BARCODE", "QR", "OCR",
        "NPS", "RATING", "RANKING",
    }
)

FIELD_TYPE_ALIASES = {
    "SELECT_ONE": "SELECT",
    "SELECT_MANY": "MULTISELECT",
    "SELECT_ONE_FROM_FILE": "REFERENCE",
    "GEOPOINT": "GPS",
    "BEGIN_REPEAT": "REPEAT",
    "TEXT_MULTILINE": "TEXTAREA",
    "DOCUMENT": "DOCUMENT_ID",
    "DOCUMENTO": "DOCUMENT_ID",
    "NUMERO_DOCUMENTO": "DOCUMENT_ID",
    "IDENTIFICATION": "DOCUMENT_ID",
    "IDENTIFICACION": "DOCUMENT_ID",
    "SUBFORM": "REPEAT",
    "SUBFORMULARIO": "REPEAT",
    "AGE_CALCULATED": "CALCULATE",
    "EDAD_CALCULADA": "CALCULATE",
    "CAMPOS_CALCULADOS": "CALCULATE",
    "PADRE-HIJO": "PARENT_CHILD",
    "VARIABLES_OCULTAS": "HIDDEN",
    "TIEMPO_ENTREVISTA": "INTERVIEW_DURATION",
    "USUARIO_CAPTURADOR": "CAPTURED_BY",
    "HISTORIAL_CAMBIOS": "CHANGE_HISTORY",
}


def normalize_field_type(value: str) -> str:
    normalized = value.strip().upper().replace(" ", "_")
    normalized = FIELD_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in FIELD_TYPES:
        raise ValueError(f"Tipo de campo no soportado: {value}")
    return normalized
