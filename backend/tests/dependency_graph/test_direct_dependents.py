from app.services.dependency_graph import DependencyGraphService


def test_get_direct_dependents_returns_children():
    service = DependencyGraphService({"cantidad": ["subtotal"], "subtotal": ["iva", "total"]})

    assert service.get_direct_dependents("cantidad") == ["subtotal"]
    assert service.get_direct_dependents("subtotal") == ["iva", "total"]


def test_get_direct_dependents_unknown_field_returns_empty_list():
    service = DependencyGraphService({"cantidad": ["subtotal"]})

    assert service.get_direct_dependents("desconocido") == []
