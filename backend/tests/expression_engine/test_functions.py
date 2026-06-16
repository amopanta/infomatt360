from app.services.expression_engine import expression_engine


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
