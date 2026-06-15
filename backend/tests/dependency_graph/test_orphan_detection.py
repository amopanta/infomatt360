from app.services.dependency_graph import DependencyGraphService


def test_detect_orphans_returns_isolated_nodes():
    service = DependencyGraphService({
        "a": ["b"],
        "b": [],
        "orphan": [],
    })

    assert service.detect_orphans() == ["orphan"]


def test_detect_orphans_returns_empty_when_all_nodes_connected():
    service = DependencyGraphService({"a": ["b"], "b": ["c"], "c": []})

    assert service.detect_orphans() == []
