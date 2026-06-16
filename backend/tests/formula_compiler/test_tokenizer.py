from app.services.formula_compiler import TokenType, formula_compiler


def test_tokenizer_field_operator_field():
    tokens = formula_compiler.tokenize("${cantidad} * ${precio}")

    assert [token.token_type for token in tokens] == [TokenType.FIELD, TokenType.OPERATOR, TokenType.FIELD]
    assert [token.value for token in tokens] == ["cantidad", "*", "precio"]


def test_tokenizer_function_and_comparison():
    tokens = formula_compiler.tokenize("if(${edad} >= 18, true(), false())")

    assert tokens[0].token_type == TokenType.IDENTIFIER
    assert tokens[0].value == "if"
    assert any(token.value == ">=" for token in tokens)
