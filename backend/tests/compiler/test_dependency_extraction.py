from app.services.form_compiler import form_compiler


def test_extract_dependencies_simple_expression():
    dependencies = form_compiler._extract_dependencies("${cantidad} * ${precio}")
    assert dependencies == ["cantidad", "precio"]


def test_extract_dependencies_removes_duplicates_and_sorts():
    dependencies = form_compiler._extract_dependencies("${precio} + ${cantidad} + ${precio}")
    assert dependencies == ["cantidad", "precio"]


def test_compile_builds_expression_map_with_dependencies():
    template = {
        "id": "tpl-test",
        "name": "Test",
        "fields": [
            {"name": "cantidad", "label": "Cantidad", "type": "number"},
            {"name": "precio", "label": "Precio", "type": "number"},
            {"name": "subtotal", "label": "Subtotal", "type": "calculate", "config": {"calculate": "${cantidad} * ${precio}"}},
        ],
    }

    package = form_compiler.compile(template)

    expression = package.expression_map["subtotal.calculate"]
    assert expression.dependencies == ["cantidad", "precio"]
