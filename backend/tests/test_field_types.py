import pytest
from pydantic import ValidationError

from app.core.field_types import FIELD_TYPES
from app.schemas.builder import BuilderComponentCreate
from app.services.form_compiler import CompilerError, form_compiler


EXCEL_FIELD_TYPES = {
    "TEXT", "TEXTAREA", "INTEGER", "DECIMAL", "SELECT", "MULTISELECT",
    "DROPDOWN", "DATE", "TIME", "DATETIME", "IMAGE", "AUDIO", "VIDEO",
    "GPS", "GEOTRACE", "GEOSHAPE", "REPEAT", "MATRIX", "CALCULATE",
    "REFERENCE", "BARCODE", "QR", "SIGNATURE", "NPS", "RATING", "RANKING",
}

ENRICHED_EXCEL_FIELD_TYPES = EXCEL_FIELD_TYPES | {
    "UUID", "RESPONSE_ID", "EMAIL", "PHONE", "URL", "DOCUMENT_ID", "YEAR", "MONTH", "WEEK",
    "PERCENTAGE", "CURRENCY", "LIKERT_5", "LIKERT_7", "PDF", "MULTIFILE",
    "PARENT_CHILD", "LOOKUP", "HIDDEN", "INTERVIEW_DURATION", "CAPTURED_BY",
    "CHANGE_HISTORY",
}


def test_catalog_covers_every_type_from_shared_spreadsheet():
    assert EXCEL_FIELD_TYPES <= FIELD_TYPES


def test_catalog_covers_every_field_from_enriched_spreadsheet():
    assert ENRICHED_EXCEL_FIELD_TYPES <= FIELD_TYPES


def test_builder_normalizes_known_type_and_rejects_unknown_type():
    payload = BuilderComponentCreate(template_id="template", component_type=" datetime ", name="fecha", label="Fecha")
    assert payload.component_type == "DATETIME"

    with pytest.raises(ValidationError, match="Tipo de campo no soportado"):
        BuilderComponentCreate(template_id="template", component_type="INVENTADO", name="x", label="X")


@pytest.mark.parametrize(
    ("source_type", "canonical_type"),
    [("select_one", "SELECT"), ("select_many", "MULTISELECT"), ("geopoint", "GPS"), ("begin_repeat", "REPEAT"), ("documento", "DOCUMENT_ID")],
)
def test_builder_normalizes_kobo_aliases(source_type, canonical_type):
    payload = BuilderComponentCreate(template_id="template", component_type=source_type, name="campo", label="Campo")
    assert payload.component_type == canonical_type


def test_compiler_rejects_unknown_type():
    with pytest.raises(CompilerError, match="Tipo invalido en campo x"):
        form_compiler.compile({"id": "t", "fields": [{"name": "x", "type": "INVENTADO"}]})
