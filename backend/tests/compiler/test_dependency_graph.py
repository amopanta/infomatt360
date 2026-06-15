from app.services.form_compiler import form_compiler


def test_dependency_graph_chain_and_branches():
    template = {
        "id": "tpl-graph",
        "name": "Graph Test",
        "fields": [
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "precio", "label": "Precio", "type": "number"},
            {"name": "subtotal", "label": "Subtotal", "type": "calculate", "config": {"calculate": "${cantidad} * ${precio}"}},
            {"name": "iva", "label": "IVA", "type": "calculate", "config": {"calculate": "${subtotal} * 0.19"}},
            {"name": "total", "label": "Total", "type": "calculate", "config": {"calculate": "${subtotal} + ${iva}"}},
        ],
    }

    package = form_compiler.compile(template)

    assert package.dependency_graph["cantidad"] == ["subtotal"]
    assert package.dependency_graph["precio"] == ["subtotal"]
    assert package.dependency_graph["subtotal"] == ["iva", "total"]
    assert package.dependency_graph["iva"] == ["total"]
