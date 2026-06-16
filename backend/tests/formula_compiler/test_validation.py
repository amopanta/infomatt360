import pytest

from app.services.formula_compiler import FormulaCompilerError, formula_compiler


def test_validate_expression_accepts_known_fields():
    formula_compiler.validate_expression("${cantidad} * ${precio}", known_fields={"cantidad", "precio"})


def test_validate_expression_rejects_unknown_field():
    with pytest.raises(FormulaCompilerError, match="Campo inexistente"):
        formula_compiler.validate_expression("${cantida} * ${precio}", known_fields={"cantidad", "precio"})


def test_validate_expression_rejects_unbalanced_parentheses():
    with pytest.raises(FormulaCompilerError, match="Parentesis desbalanceados"):
        formula_compiler.validate_expression("(${cantidad} * ${precio}")


def test_validate_expression_rejects_unknown_function():
    with pytest.raises(FormulaCompilerError, match="Funcion desconocida"):
        formula_compiler.validate_expression("desconocida(${cantidad})")
