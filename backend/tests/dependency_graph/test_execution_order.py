from app.services.dependency_graph import DependencyGraphService


def test_execution_order_keeps_dependencies_before_dependents():
    service = DependencyGraphService({
        "cantidad": ["subtotal"],
        "subtotal": ["iva"],
        "iva": ["total"],
        "total": [],
    })

    assert service.get_execution_order("cantidad") == ["subtotal", "iva", "total"]


def test_execution_order_handles_branches():
    service = DependencyGraphService({
        "a": ["b", "c"],
        "b": ["d"],
        "c": ["e"],
        "d": [],
        "e": [],
    })

    assert service.get_execution_order("a") == ["b", "d", "c", "e"]
