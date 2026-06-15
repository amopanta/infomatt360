from app.services.dependency_graph import DependencyGraphService


def test_get_all_dependents_returns_transitive_branch():
    service = DependencyGraphService({
        "cantidad": ["subtotal"],
        "precio": ["subtotal"],
        "subtotal": ["iva", "total"],
        "iva": ["total"],
        "total": [],
    })

    assert service.get_all_dependents("cantidad") == ["subtotal", "iva", "total"]


def test_get_all_dependents_avoids_duplicates():
    service = DependencyGraphService({
        "a": ["b", "c"],
        "b": ["d"],
        "c": ["d"],
        "d": [],
    })

    assert service.get_all_dependents("a") == ["b", "c", "d"]
