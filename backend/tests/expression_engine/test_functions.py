import pytest

from app.services.expression_engine import ExpressionEngineError, expression_engine


def test_if_function():
    result = expression_engine.evaluate_calculate("if(${edad} >= 18, 'adulto', 'menor')", {"edad": 20})

    assert result == "adulto"


def test_sum_function():
    assert expression_engine.evaluate_calculate("sum(${a}, ${b}, 3)", {"a": 1, "b": 2}) == 6


def test_round_function():
    assert expression_engine.evaluate_calculate("round(${valor}, 2)", {"valor": 3.14159}) == 3.14


def test_concat_function():
    assert expression_engine.evaluate_calculate("concat('A', ${codigo})", {"codigo": 123}) == "A123"


def test_selected_function_with_string_choices():
    assert expression_engine.evaluate_relevant("selected(${opciones}, 'b')", {"opciones": "a b c"}) is True


def test_pulldata_reads_versioned_runtime_cache():
    context = {
        "municipio_id": 2,
        "__pulldata__": {
            "municipios": {
                "version": "2026-06-22",
                "rows": [
                    {"codigo": 1, "nombre": "Medellin"},
                    {"codigo": 2, "nombre": "Bogota"},
                ],
            }
        },
    }

    result = expression_engine.evaluate_calculate(
        "pulldata('municipios', 'nombre', 'codigo', ${municipio_id})",
        context,
    )

    assert result == "Bogota"


def test_pulldata_returns_none_when_row_does_not_exist():
    context = {"municipio_id": 99, "__pulldata__": {"municipios": []}}

    assert expression_engine.evaluate_calculate(
        "pulldata('municipios', 'nombre', 'codigo', ${municipio_id})",
        context,
    ) is None


def test_pulldata_rejects_missing_source():
    with pytest.raises(ExpressionEngineError, match="Fuente pulldata no disponible: municipios"):
        expression_engine.evaluate_calculate(
            "pulldata('municipios', 'nombre', 'codigo', ${municipio_id})",
            {"municipio_id": 1},
        )
