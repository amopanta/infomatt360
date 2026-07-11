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
            {"name": "edad", "label": "Edad", "type": "number"},
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


def test_recalculate_affected_evaluates_rule_on_changed_field():
    template = {
        "id": "runner-local-rule",
        "name": "Runner Local Rule",
        "fields": [
            {"name": "edad", "label": "Edad", "type": "number", "config": {"constraint": "${edad} >= 0"}},
        ],
    }
    runner = RuntimeExpressionRunner(form_compiler.compile(template))

    assert runner.recalculate_affected("edad", {"edad": 10})["edad.constraint"] is True
    assert runner.recalculate_affected("edad", {"edad": -1})["edad.constraint"] is False


def test_recalculate_affected_resolves_pulldata_from_runtime_context():
    template = {
        "id": "runner-pulldata",
        "name": "Runner Pulldata",
        "fields": [
            {"name": "municipio_id", "label": "Municipio", "type": "number"},
            {
                "name": "municipio_nombre",
                "label": "Nombre municipio",
                "type": "calculate",
                "config": {
                    "calculate": "pulldata('municipios', 'nombre', 'codigo', ${municipio_id})"
                },
            },
        ],
    }
    runner = RuntimeExpressionRunner(form_compiler.compile(template))
    context = {
        "municipio_id": 2,
        "__pulldata__": {
            "municipios": [
                {"codigo": 1, "nombre": "Medellin"},
                {"codigo": 2, "nombre": "Bogota"},
            ]
        },
    }

    assert runner.recalculate_affected("municipio_id", context) == {"municipio_nombre": "Bogota"}
