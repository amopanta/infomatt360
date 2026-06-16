from app.services.expression_engine import expression_engine


def test_evaluate_relevant_true():
    assert expression_engine.evaluate_relevant("${edad} >= 18", {"edad": 20}) is True


def test_evaluate_relevant_false():
    assert expression_engine.evaluate_relevant("${edad} >= 18", {"edad": 17}) is False


def test_evaluate_constraint_true():
    assert expression_engine.evaluate_constraint("${edad} >= 0", {"edad": 0}) is True


def test_evaluate_required_boolean_and_expression():
    assert expression_engine.evaluate_required(True, {}) is True
    assert expression_engine.evaluate_required("${respuesta} = 1", {"respuesta": 1}) is True


def test_evaluate_choice_filter():
    assert expression_engine.evaluate_choice_filter("${departamento} = 5", {"departamento": 5}) is True
