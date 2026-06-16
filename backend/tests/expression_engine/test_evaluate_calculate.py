from app.services.expression_engine import expression_engine


def test_evaluate_multiply_calculate():
    result = expression_engine.evaluate_calculate("${cantidad} * ${precio}", {"cantidad": 5, "precio": 10})

    assert result == 50


def test_evaluate_respects_precedence():
    result = expression_engine.evaluate_calculate("${a} + ${b} * ${c}", {"a": 2, "b": 3, "c": 4})

    assert result == 14


def test_evaluate_parentheses():
    result = expression_engine.evaluate_calculate("(${a} + ${b}) * ${c}", {"a": 2, "b": 3, "c": 4})

    assert result == 20
