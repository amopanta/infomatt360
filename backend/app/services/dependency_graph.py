"""
Proyecto: InfoMatt360
Modulo: Dependency Graph v1
Responsabilidad: Consultar dependencias del Runtime Package para recalculo selectivo.
"""

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactScore:
    field: str
    direct_dependents: int
    indirect_dependents: int
    impact: str


@dataclass(frozen=True)
class GraphProfile:
    nodes: int
    edges: int
    max_depth: int
    high_impact_nodes: list[str]
    orphan_nodes: list[str]


class DependencyGraphService:
    """Servicio de navegacion y analisis sobre un grafo dirigido.

    El grafo esperado tiene forma:
        campo_origen -> [campos_dependientes]

    Ejemplo:
        cantidad -> subtotal -> iva -> total
    """

    def __init__(self, graph: dict[str, list[str]]):
        self.graph = {node: sorted(set(children)) for node, children in graph.items()}
        self.nodes = self._collect_nodes()

    def get_direct_dependents(self, field: str) -> list[str]:
        """Retorna los dependientes directos de un campo."""
        return self.graph.get(field, [])

    def get_all_dependents(self, field: str) -> list[str]:
        """Retorna dependientes directos e indirectos sin duplicados.

        Usa BFS para mantener un orden estable y evitar recorrer todo el
        formulario cuando solo se necesita la rama afectada.
        """
        visited: set[str] = set()
        result: list[str] = []
        queue: deque[str] = deque(self.get_direct_dependents(field))

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            queue.extend(self.get_direct_dependents(node))

        return result

    def get_execution_order(self, field: str) -> list[str]:
        """Calcula orden de ejecucion para dependientes afectados.

        Garantiza que un calculo padre se ejecute antes que sus dependientes.
        """
        affected = set(self.get_all_dependents(field))
        ordered: list[str] = []
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            if node in affected:
                ordered.append(node)
            for child in self.get_direct_dependents(node):
                visit(child)

        for child in self.get_direct_dependents(field):
            visit(child)

        return ordered

    def get_impact_score(self, field: str) -> ImpactScore:
        """Clasifica impacto segun cantidad de dependientes afectados."""
        direct = len(self.get_direct_dependents(field))
        indirect = len(self.get_all_dependents(field))
        impact = "LOW"
        if indirect >= 25 or direct >= 10:
            impact = "HIGH"
        elif indirect >= 8 or direct >= 4:
            impact = "MEDIUM"
        return ImpactScore(field=field, direct_dependents=direct, indirect_dependents=indirect, impact=impact)

    def detect_orphans(self) -> list[str]:
        """Detecta nodos sin entradas ni salidas dentro del grafo."""
        incoming = self._incoming_counts()
        return sorted(node for node in self.nodes if incoming.get(node, 0) == 0 and len(self.graph.get(node, [])) == 0)

    def build_graph_profile(self) -> GraphProfile:
        """Construye perfil del grafo para detectar riesgo antes de publicar."""
        edges = sum(len(children) for children in self.graph.values())
        high_impact_nodes = [node for node in sorted(self.nodes) if self.get_impact_score(node).impact == "HIGH"]
        return GraphProfile(nodes=len(self.nodes), edges=edges, max_depth=self._max_depth(), high_impact_nodes=high_impact_nodes, orphan_nodes=self.detect_orphans())

    def _collect_nodes(self) -> set[str]:
        nodes = set(self.graph.keys())
        for children in self.graph.values():
            nodes.update(children)
        return nodes

    def _incoming_counts(self) -> dict[str, int]:
        incoming = {node: 0 for node in self.nodes}
        for children in self.graph.values():
            for child in children:
                incoming[child] = incoming.get(child, 0) + 1
        return incoming

    def _max_depth(self) -> int:
        def depth(node: str, visited: set[str]) -> int:
            if node in visited:
                return 0
            children = self.get_direct_dependents(node)
            if not children:
                return 1
            return 1 + max(depth(child, visited | {node}) for child in children)

        if not self.nodes:
            return 0
        return max(depth(node, set()) for node in self.nodes)
