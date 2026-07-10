import pytest

from app.services.form_compiler import CompilerError, form_compiler


def test_cycle_detection_blocks_publication():
    template = {
        "id": "tpl-cycle",
        "name": "Cycle Test",
        "fields": [
            {"name": "a", "label": "A", "type": "calculate", "config": {"calculate": "${b} + 1"}},
            {"name": "b", "label": "B", "type": "calculate", "config": {"calculate": "${c} + 1"}},
            {"name": "c", "label": "C", "type": "calculate", "config": {"calculate": "${a} + 1"}},
        ],
    }

    with pytest.raises(CompilerError, match="Dependencia circular"):
        form_compiler.compile(template)


def test_self_reference_is_detected_as_cycle():
    template = {
        "id": "tpl-self-cycle",
        "name": "Self Cycle Test",
        "fields": [
            {"name": "total", "label": "Total", "type": "calculate", "config": {"calculate": "${total} + 1"}},
        ],
    }

    with pytest.raises(CompilerError, match="Dependencia circular"):
        form_compiler.compile(template)


def test_self_reference_in_validation_rule_is_not_a_cycle():
    template = {
        "id": "tpl-self-validation",
        "name": "Self Validation Test",
        "fields": [
            {"name": "edad", "label": "Edad", "type": "number", "config": {"constraint": "${edad} >= 0"}},
        ],
    }

    package = form_compiler.compile(template)

    assert package.dependency_graph["edad"] == []
