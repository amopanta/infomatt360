import pytest

from app.services.form_compiler import CompilerError, form_compiler


def make_template(fields):
    return {"id": "validation-test", "name": "Validation Test", "fields": fields}


def test_compile_rejects_empty_field_list():
    with pytest.raises(CompilerError, match="al menos un campo"):
        form_compiler.compile(make_template([]))


def test_compile_rejects_missing_field_name():
    with pytest.raises(CompilerError, match="Campo sin nombre"):
        form_compiler.compile(make_template([{"label": "Sin nombre", "type": "text"}]))


def test_compile_rejects_invalid_field_name():
    with pytest.raises(CompilerError, match="Nombre de campo invalido"):
        form_compiler.compile(make_template([{"name": "cantidad total", "type": "number"}]))


def test_compile_rejects_duplicate_field_name():
    fields = [
        {"name": "cantidad", "type": "number"},
        {"name": "cantidad", "type": "number"},
    ]

    with pytest.raises(CompilerError, match="Nombre de campo duplicado: cantidad"):
        form_compiler.compile(make_template(fields))


def test_compile_rejects_unknown_expression_reference():
    fields = [
        {"name": "cantidad", "type": "number"},
        {"name": "total", "type": "calculate", "config": {"calculate": "${cantida} * 2"}},
    ]

    with pytest.raises(CompilerError, match="Expresion invalida en total.calculate: Campo inexistente: cantida"):
        form_compiler.compile(make_template(fields))


def test_compile_rejects_malformed_expression():
    fields = [
        {"name": "cantidad", "type": "number"},
        {"name": "total", "type": "calculate", "config": {"calculate": "(${cantidad} * 2"}},
    ]

    with pytest.raises(CompilerError, match="Expresion invalida en total.calculate: Parentesis desbalanceados"):
        form_compiler.compile(make_template(fields))
