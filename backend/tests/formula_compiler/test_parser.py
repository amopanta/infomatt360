from app.services.formula_compiler import formula_compiler


def test_parse_parenthesized_expression():
    ast = formula_compiler.build_ast("(${cantidad} + ${extra}) * ${precio}")

    assert ast.node_type == "MULTIPLY"
    assert ast.children[0].node_type == "ADD"
    assert ast.children[1].value == "precio"


def test_parse_comparison_expression():
    ast = formula_compiler.build_ast("${edad} >= 18")

    assert ast.node_type == "GREATER_EQUAL"
    assert ast.children[0].value == "edad"
    assert ast.children[1].value == 18.0
