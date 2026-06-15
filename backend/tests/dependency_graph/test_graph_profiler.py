from app.services.dependency_graph import DependencyGraphService


def test_graph_profile_counts_nodes_edges_depth_and_orphans():
    service = DependencyGraphService({
        "a": ["b"],
        "b": ["c"],
        "c": [],
        "orphan": [],
    })

    profile = service.build_graph_profile()

    assert profile.nodes == 4
    assert profile.edges == 2
    assert profile.max_depth == 3
    assert profile.orphan_nodes == ["orphan"]


def test_graph_profile_detects_high_impact_nodes():
    graph = {"root": [f"n{i}" for i in range(10)]}
    for i in range(10):
        graph[f"n{i}"] = []

    profile = DependencyGraphService(graph).build_graph_profile()

    assert profile.high_impact_nodes == ["root"]
