from app.services.form_compiler import form_compiler
from app.services.runtime_expression_runner import RuntimeExpressionRunner


def build_runtime_package():
    template = {
        "id": "runner-test",
        "name": "Runner Test",
        "fields": [
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "precio", "label": "Precio", "type": "number"},
            {"name": "subtotal", "label": "Subtotal", "type": "calculate", "config": {"calculate": "${cantidad} * ${precio}"}},
            {"name": "iva", "label": "IVA", "type": "calculate", "config": {"calculate": "${subtotal} * 0.19"}},
            {"name": "total", "label": "Total", "type": "calculate", "config": {"calculate": "${subtotal} + ${iva}"}},
            {"name": "mayor_edad", "label": "Mayor edad", "type": "text", "config": {"relevant": "${edad} >= 18"}},
        ],
    }
    return form_compiler.compile(template)


def test_evaluate_expression_key():
    runner = RuntimeExpressionRunner(build_runtime_package())

    assert runner.evaluate_expression_key("subtotal.calculate", {"cantidad": 5, "precio": 10}) == 50


def test_recalculate_affected_calculate_chain():
    runner = RuntimeExpressionRunner(build_runtime_package())

    results = runner.recalculate_affected("cantidad", {"cantidad": 5, "precio": 10})

    assert results["subtotal"] == 50
    assert results["iva"] == 9.5
    assert results["total"] == 59.5


def test_recalculate_affected_non_calculate_rule():
    runner = RuntimeExpressionRunner(build_runtime_package())

    results = runner.recalculate_affected("edad", {"edad": 20})

    assert results["mayor_edad.relevant"] is True
