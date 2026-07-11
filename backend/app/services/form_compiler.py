"""
Proyecto: InfoMatt360
Modulo: Form Compiler v1
Responsabilidad: Convertir Template JSON del Builder en Runtime Package optimizado.
"""

import re
from collections import defaultdict
from typing import Any

from app.core.field_types import normalize_field_type
from app.schemas.runtime_package import RuntimeExpression, RuntimeFieldSchema, RuntimePackage, RuntimePackageManifest, RuntimePerformanceProfile, RuntimeSchema
from app.services.formula_compiler import FormulaCompilerError, formula_compiler

FIELD_REF_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_\.\-]+)\}")
FIELD_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_\.\-]*$")
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
        self._validate_expressions(expression_map, {field.name for field in fields})
        dependency_graph = self._build_dependency_graph(expression_map)
        self._assert_no_cycles(dependency_graph)
        profile = self._build_performance_profile(fields, expression_map, dependency_graph)
        schema = RuntimeSchema(template_id=str(template.get("id", "")), name=str(template.get("name", "Formulario")), fields=fields, layout=template.get("layout", {}))
        manifest = RuntimePackageManifest(template_id=schema.template_id, name=schema.name, generated_files=["schema.json", "dependency_graph.json", "expression_map.json", "pulldata_map.json", "performance_profile.json", "manifest.json", "version.json"])
        return RuntimePackage(manifest=manifest, schema=schema, dependency_graph=dependency_graph, expression_map=expression_map, pulldata_map=template.get("pulldata_map", {}), performance_profile=profile, version={"compiler": "1.0.0", "runtime_package": "1.0.0"})

    def _extract_fields(self, template: dict[str, Any]) -> list[RuntimeFieldSchema]:
        raw_fields = template.get("fields", [])
        if not isinstance(raw_fields, list) or not raw_fields:
            raise CompilerError("La plantilla debe contener al menos un campo")

        fields: list[RuntimeFieldSchema] = []
        known_names: set[str] = set()
        for index, raw in enumerate(raw_fields):
            if not isinstance(raw, dict):
                raise CompilerError(f"Campo invalido en posicion {index}")
            raw_name = raw.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise CompilerError(f"Campo sin nombre en posicion {index}")
            name = raw_name.strip()
            if not FIELD_NAME_PATTERN.fullmatch(name):
                raise CompilerError(f"Nombre de campo invalido: {name}")
            if name in known_names:
                raise CompilerError(f"Nombre de campo duplicado: {name}")
            known_names.add(name)
            try:
                field_type = normalize_field_type(str(raw.get("type", "text")))
            except ValueError as exc:
                raise CompilerError(f"Tipo invalido en campo {name}: {exc}") from exc
            fields.append(RuntimeFieldSchema(name=name, label=str(raw.get("label", name)), type=field_type, required=bool(raw.get("required", False)), page_id=raw.get("page_id"), section_id=raw.get("section_id"), config=raw.get("config", {})))
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

    def _validate_expressions(self, expression_map: dict[str, RuntimeExpression], known_fields: set[str]) -> None:
        """Bloquea paquetes con formulas invalidas o referencias inexistentes."""
        for expression_key, expression in expression_map.items():
            try:
                formula_compiler.validate_expression(expression.expression, known_fields=known_fields)
            except FormulaCompilerError as exc:
                raise CompilerError(f"Expresion invalida en {expression_key}: {exc}") from exc

    def _build_dependency_graph(self, expression_map: dict[str, RuntimeExpression]) -> dict[str, list[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for expression in expression_map.values():
            for dependency in expression.dependencies:
                # Una regla de validacion puede consultar el valor del mismo
                # campo sin crear una dependencia de recalculo. En cambio, un
                # calculate autorreferenciado si es un ciclo real.
                if dependency == expression.field and expression.expression_type != "calculate":
                    continue
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
