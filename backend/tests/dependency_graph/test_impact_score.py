from app.services.dependency_graph import DependencyGraphService


def test_low_impact_score():
    service = DependencyGraphService({"a": ["b"], "b": []})

    score = service.get_impact_score("a")

    assert score.direct_dependents == 1
    assert score.indirect_dependents == 1
    assert score.impact == "LOW"


def test_medium_impact_score():
    service = DependencyGraphService({
        "a": ["b", "c", "d", "e"],
        "b": [],
        "c": [],
        "d": [],
        "e": [],
    })

    assert service.get_impact_score("a").impact == "MEDIUM"


def test_high_impact_score():
    graph = {"root": [f"n{i}" for i in range(10)]}
    for i in range(10):
        graph[f"n{i}"] = []

    assert DependencyGraphService(graph).get_impact_score("root").impact == "HIGH"
