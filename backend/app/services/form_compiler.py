"""
Proyecto: InfoMatt360
Modulo: Form Compiler v1
Responsabilidad: Convertir Template JSON del Builder en Runtime Package optimizado.
"""

import re
from collections import defaultdict
from typing import Any

from app.schemas.runtime_package import RuntimeExpression, RuntimeFieldSchema, RuntimePackage, RuntimePackageManifest, RuntimePerformanceProfile, RuntimeSchema

FIELD_REF_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_\.\-]+)\}")
EXPRESSION_KEYS = ("calculate", "relevant", "constraint", "required", "choice_filter")


class CompilerError(Exception):
    """Error controlado de compilacion que bloquea publicacion del formulario."""


class FormCompiler:
    """Compila formularios Builder a Runtime Package.

    El compiler evita que Runtime interprete toda la estructura de diseno en tiempo real.
    Su salida esta optimizada para renderizado progresivo, recalculo selectivo y offline.
    """

    def compile(self, template: dict[str, Any]) -> RuntimePackage:
        fields = self._extract_fields(template)
        expression_map = self._extract_expressions(fields)
        dependency_graph = self._build_dependency_graph(expression_map)
        self._assert_no_cycles(dependency_graph)
        profile = self._build_performance_profile(fields, expression_map, dependency_graph)
        schema = RuntimeSchema(template_id=str(template.get("id", "")), name=str(template.get("name", "Formulario")), fields=fields, layout=template.get("layout", {}))
        manifest = RuntimePackageManifest(template_id=schema.template_id, name=schema.name, generated_files=["schema.json", "dependency_graph.json", "expression_map.json", "pulldata_map.json", "performance_profile.json", "manifest.json", "version.json"])
        return RuntimePackage(manifest=manifest, schema=schema, dependency_graph=dependency_graph, expression_map=expression_map, pulldata_map=template.get("pulldata_map", {}), performance_profile=profile, version={"compiler": "1.0.0", "runtime_package": "1.0.0"})

    def _extract_fields(self, template: dict[str, Any]) -> list[RuntimeFieldSchema]:
        raw_fields = template.get("fields", [])
        fields: list[RuntimeFieldSchema] = []
        for raw in raw_fields:
            fields.append(RuntimeFieldSchema(name=str(raw.get("name")), label=str(raw.get("label", raw.get("name"))), type=str(raw.get("type", "text")), required=bool(raw.get("required", False)), page_id=raw.get("page_id"), section_id=raw.get("section_id"), config=raw.get("config", {})))
        return fields

    def _extract_expressions(self, fields: list[RuntimeFieldSchema]) -> dict[str, RuntimeExpression]:
        expression_map: dict[str, RuntimeExpression] = {}
        for field in fields:
            for key in EXPRESSION_KEYS:
                expression = field.config.get(key)
                if isinstance(expression, str) and expression.strip():
                    expression_map[f"{field.name}.{key}"] = RuntimeExpression(field=field.name, expression_type=key, expression=expression, dependencies=self._extract_dependencies(expression))
        return expression_map

    def _extract_dependencies(self, expression: str) -> list[str]:
        return sorted(set(FIELD_REF_PATTERN.findall(expression)))

    def _build_dependency_graph(self, expression_map: dict[str, RuntimeExpression]) -> dict[str, list[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for expression in expression_map.values():
            for dependency in expression.dependencies:
                graph[dependency].add(expression.field)
            graph.setdefault(expression.field, set())
        return {field: sorted(dependents) for field, dependents in graph.items()}

    def _assert_no_cycles(self, graph: dict[str, list[str]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()
        path: list[str] = []

        def visit(node: str) -> None:
            if node in visiting:
                cycle_start = path.index(node) if node in path else 0
                cycle = " -> ".join(path[cycle_start:] + [node])
                raise CompilerError(f"Dependencia circular detectada: {cycle}")
            if node in visited:
                return
            visiting.add(node)
            path.append(node)
            for child in graph.get(node, []):
                visit(child)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def _build_performance_profile(self, fields: list[RuntimeFieldSchema], expression_map: dict[str, RuntimeExpression], graph: dict[str, list[str]]) -> RuntimePerformanceProfile:
        repeats = sum(1 for field in fields if field.type.upper() == "REPEAT")
        edges = sum(len(children) for children in graph.values())
        complexity = "LOW"
        recommendations: list[str] = []
        if len(fields) > 200 or len(expression_map) > 100 or repeats > 5:
            complexity = "HIGH"
            recommendations.extend(["Activar render por seccion", "Activar repeat virtualizado", "Activar cache pulldata"])
        elif len(fields) > 80 or len(expression_map) > 30:
            complexity = "MEDIUM"
            recommendations.append("Usar paginas y secciones")
        return RuntimePerformanceProfile(fields=len(fields), repeats=repeats, expressions=len(expression_map), dependency_edges=edges, complexity=complexity, recommendations=recommendations)


form_compiler = FormCompiler()
