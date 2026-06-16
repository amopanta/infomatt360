from app.services.formula_compiler import formula_compiler


def test_extract_references_unique_sorted():
    refs = formula_compiler.extract_references("${precio} + ${cantidad} + ${precio}")

    assert refs == ["cantidad", "precio"]


def test_extract_references_empty_when_no_fields():
    assert formula_compiler.extract_references("1 + 2") == []
