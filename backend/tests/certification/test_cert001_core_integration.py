"""CERT-001 Core Integration.

Valida el flujo completo:
Builder Template -> Compiler -> Runtime Package -> Dependency Graph -> Expression Engine -> Runtime Runner.
"""

from app.services.form_compiler import form_compiler
from app.services.runtime_expression_runner import RuntimeExpressionRunner


def build_cert001_core_template():
    return {
        "id": "cert001-core",
        "name": "CERT-001 Core Integration",
        "fields": [
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "precio", "label": "Precio", "type": "number"},
            {"name": "subtotal", "label": "Subtotal", "type": "calculate", "config": {"calculate": "${cantidad} * ${precio}"}},
            {"name": "iva", "label": "IVA", "type": "calculate", "config": {"calculate": "${subtotal} * 0.19"}},
            {"name": "total", "label": "Total", "type": "calculate", "config": {"calculate": "${subtotal} + ${iva}"}},
            {"name": "mayor_edad", "label": "Mayor edad", "type": "text", "config": {"relevant": "${edad} >= 18"}},
            {"name": "edad", "label": "Edad", "type": "number", "config": {"constraint": "${edad} >= 0", "required": "true()"}},
            {"name": "municipio", "label": "Municipio", "type": "select_one", "config": {"choice_filter": "${departamento} = 5"}},
        ],
    }


def test_cert001_compile_generates_runtime_package():
    package = form_compiler.compile(build_cert001_core_template())

    assert package.manifest.template_id == "cert001-core"
    assert "subtotal.calculate" in package.expression_map
    assert "iva.calculate" in package.expression_map
    assert "total.calculate" in package.expression_map
    assert package.dependency_graph["cantidad"] == ["subtotal"]
    assert package.dependency_graph["subtotal"] == ["iva", "total"]


def test_cert001_calculation_chain_recalculates_only_affected_fields():
    package = form_compiler.compile(build_cert001_core_template())
    runner = RuntimeExpressionRunner(package)

    results = runner.recalculate_affected("cantidad", {"cantidad": 5, "precio": 10})

    assert results == {
        "subtotal": 50,
        "iva": 9.5,
        "total": 59.5,
    }


def test_cert001_relevant_false_for_minor():
    package = form_compiler.compile(build_cert001_core_template())
    runner = RuntimeExpressionRunner(package)

    results = runner.recalculate_affected("edad", {"edad": 17})

    assert results["mayor_edad.relevant"] is False
    assert results["edad.constraint"] is True
    assert results["edad.required"] is True


def test_cert001_relevant_true_for_adult():
    package = form_compiler.compile(build_cert001_core_template())
    runner = RuntimeExpressionRunner(package)

    results = runner.recalculate_affected("edad", {"edad": 20})

    assert results["mayor_edad.relevant"] is True
    assert results["edad.constraint"] is True
    assert results["edad.required"] is True


def test_cert001_choice_filter():
    package = form_compiler.compile(build_cert001_core_template())
    runner = RuntimeExpressionRunner(package)

    assert runner.recalculate_affected("departamento", {"departamento": 5})["municipio.choice_filter"] is True
    assert runner.recalculate_affected("departamento", {"departamento": 8})["municipio.choice_filter"] is False
