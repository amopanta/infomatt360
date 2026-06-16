from app.services.formula_compiler import formula_compiler


def test_build_ast_multiply_fields():
    ast = formula_compiler.build_ast("${cantidad} * ${precio}")

    assert ast.node_type == "MULTIPLY"
    assert ast.children[0].node_type == "FIELD"
    assert ast.children[0].value == "cantidad"
    assert ast.children[1].node_type == "FIELD"
    assert ast.children[1].value == "precio"


def test_build_ast_respects_precedence():
    ast = formula_compiler.build_ast("${a} + ${b} * ${c}")

    assert ast.node_type == "ADD"
    assert ast.children[0].value == "a"
    assert ast.children[1].node_type == "MULTIPLY"


def test_build_ast_function_if():
    ast = formula_compiler.build_ast("if(${edad} >= 18, true(), false())")

    assert ast.node_type == "FUNCTION"
    assert ast.value == "if"
    assert len(ast.children) == 3
    assert ast.children[0].node_type == "GREATER_EQUAL"
