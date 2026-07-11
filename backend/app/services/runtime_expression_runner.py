"""
Proyecto: InfoMatt360
Modulo: Runtime Expression Runner
Responsabilidad: Evaluar expression_map del Runtime Package usando Expression Engine.
"""

from typing import Any

from app.schemas.runtime_package import RuntimeExpression, RuntimePackage
from app.services.dependency_graph import DependencyGraphService
from app.services.expression_engine import expression_engine


class RuntimeExpressionRunner:
    """Orquesta recalculo selectivo sobre Runtime Package.

    Este servicio conecta:
    - RuntimePackage.expression_map
    - RuntimePackage.dependency_graph
    - ExpressionEngine

    Permite recalcular solo las expresiones afectadas por un cambio de campo.
    """

    def __init__(self, runtime_package: RuntimePackage):
        self.package = runtime_package
        self.graph = DependencyGraphService(runtime_package.dependency_graph)

    def evaluate_expression_key(self, expression_key: str, context: dict[str, Any]) -> Any:
        """Evalua una expresion puntual por clave expression_map."""
        expression = self.package.expression_map.get(expression_key)
        if expression is None:
            raise KeyError(f"Expresion no encontrada: {expression_key}")
        return self._evaluate_runtime_expression(expression, context)

    def recalculate_affected(self, changed_field: str, context: dict[str, Any]) -> dict[str, Any]:
        """Recalcula expresiones afectadas por el campo modificado.

        Retorna un diccionario field -> nuevo valor para expresiones calculate.
        Otros tipos de expresion se retornan como field.expression_type para no
        sobrescribir directamente el valor capturado.
        """
        results: dict[str, Any] = {}
        # Constraint, required y otras reglas locales deben reevaluarse cuando
        # cambia su propio campo. No forman aristas del grafo porque no calculan
        # un nuevo valor para ese campo.
        for expression in self._local_rules_for_field(changed_field):
            result_key = f"{changed_field}.{expression.expression_type}"
            results[result_key] = self._evaluate_runtime_expression(expression, context)

        for field in self.graph.get_execution_order(changed_field):
            for expression in self._expressions_for_field(field):
                value = self._evaluate_runtime_expression(expression, {**context, **results})
                result_key = field if expression.expression_type == "calculate" else f"{field}.{expression.expression_type}"
                results[result_key] = value
        return results

    def _expressions_for_field(self, field: str) -> list[RuntimeExpression]:
        return [expression for expression in self.package.expression_map.values() if expression.field == field]

    def _local_rules_for_field(self, field: str) -> list[RuntimeExpression]:
        return [
            expression
            for expression in self._expressions_for_field(field)
            if expression.expression_type != "calculate"
        ]

    def _evaluate_runtime_expression(self, expression: RuntimeExpression, context: dict[str, Any]) -> Any:
        if expression.expression_type == "calculate":
            return expression_engine.evaluate_calculate(expression.expression, context)
        if expression.expression_type == "required":
            return expression_engine.evaluate_required(expression.expression, context)
        if expression.expression_type == "relevant":
            return expression_engine.evaluate_relevant(expression.expression, context)
        if expression.expression_type == "constraint":
            return expression_engine.evaluate_constraint(expression.expression, context)
        if expression.expression_type == "choice_filter":
            return expression_engine.evaluate_choice_filter(expression.expression, context)
        return expression_engine.evaluate_expression(expression.expression, context)
