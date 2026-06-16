"""
Proyecto: InfoMatt360
Modulo: Expression Engine v1
Responsabilidad: Evaluar AST generado por Formula Compiler sobre un contexto de captura.
"""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from app.services.formula_compiler import ASTNode, formula_compiler


class ExpressionEngineError(Exception):
    """Error controlado durante evaluacion de expresiones."""


class ExpressionEngine:
    """Motor de evaluacion para reglas de formularios.

    Alcance v1:
    - operadores aritmeticos;
    - operadores comparadores;
    - campos desde contexto;
    - funciones basicas: if, sum, count, round, concat, selected, true, false, today, now.
    """

    def evaluate(self, ast: ASTNode, context: dict[str, Any]) -> Any:
        """Evalua un AST sobre un contexto de valores."""
        node_type = ast.node_type

        if node_type == "FIELD":
            return context.get(str(ast.value))
        if node_type == "NUMBER":
            return ast.value
        if node_type == "STRING":
            return ast.value
        if node_type == "IDENTIFIER":
            return context.get(str(ast.value))

        if node_type == "ADD":
            return self.evaluate(ast.children[0], context) + self.evaluate(ast.children[1], context)
        if node_type == "SUBTRACT":
            return self.evaluate(ast.children[0], context) - self.evaluate(ast.children[1], context)
        if node_type == "MULTIPLY":
            return self.evaluate(ast.children[0], context) * self.evaluate(ast.children[1], context)
        if node_type == "DIVIDE":
            denominator = self.evaluate(ast.children[1], context)
            if denominator == 0:
                raise ExpressionEngineError("Division por cero")
            return self.evaluate(ast.children[0], context) / denominator

        if node_type == "EQUAL":
            return self.evaluate(ast.children[0], context) == self.evaluate(ast.children[1], context)
        if node_type == "NOT_EQUAL":
            return self.evaluate(ast.children[0], context) != self.evaluate(ast.children[1], context)
        if node_type == "GREATER_THAN":
            return self.evaluate(ast.children[0], context) > self.evaluate(ast.children[1], context)
        if node_type == "LESS_THAN":
            return self.evaluate(ast.children[0], context) < self.evaluate(ast.children[1], context)
        if node_type == "GREATER_EQUAL":
            return self.evaluate(ast.children[0], context) >= self.evaluate(ast.children[1], context)
        if node_type == "LESS_EQUAL":
            return self.evaluate(ast.children[0], context) <= self.evaluate(ast.children[1], context)

        if node_type == "FUNCTION":
            return self._evaluate_function(str(ast.value), ast.children, context)

        raise ExpressionEngineError(f"Nodo no soportado: {node_type}")

    def evaluate_expression(self, expression: str, context: dict[str, Any], known_fields: set[str] | None = None) -> Any:
        """Compila y evalua una expresion textual en una sola llamada."""
        ast = formula_compiler.build_ast(expression, known_fields=known_fields)
        return self.evaluate(ast, context)

    def evaluate_calculate(self, expression: str, context: dict[str, Any], known_fields: set[str] | None = None) -> Any:
        """Evalua expresion calculate."""
        return self.evaluate_expression(expression, context, known_fields)

    def evaluate_required(self, expression: str | bool, context: dict[str, Any], known_fields: set[str] | None = None) -> bool:
        """Evalua regla required; acepta booleano directo o expresion."""
        if isinstance(expression, bool):
            return expression
        return bool(self.evaluate_expression(expression, context, known_fields))

    def evaluate_relevant(self, expression: str | bool, context: dict[str, Any], known_fields: set[str] | None = None) -> bool:
        """Evalua regla relevant para mostrar/ocultar campos o secciones."""
        if isinstance(expression, bool):
            return expression
        return bool(self.evaluate_expression(expression, context, known_fields))

    def evaluate_constraint(self, expression: str | bool, context: dict[str, Any], known_fields: set[str] | None = None) -> bool:
        """Evalua constraint; True significa valido."""
        if isinstance(expression, bool):
            return expression
        return bool(self.evaluate_expression(expression, context, known_fields))

    def evaluate_choice_filter(self, expression: str | bool, context: dict[str, Any], known_fields: set[str] | None = None) -> bool:
        """Evalua choice_filter para listas dependientes."""
        if isinstance(expression, bool):
            return expression
        return bool(self.evaluate_expression(expression, context, known_fields))

    def _evaluate_function(self, name: str, args: list[ASTNode], context: dict[str, Any]) -> Any:
        evaluated = [self.evaluate(arg, context) for arg in args]

        if name == "if":
            if len(args) != 3:
                raise ExpressionEngineError("if requiere 3 argumentos")
            condition = bool(self.evaluate(args[0], context))
            return self.evaluate(args[1], context) if condition else self.evaluate(args[2], context)
        if name == "sum":
            return sum(self._flatten_numbers(evaluated))
        if name == "count":
            return len([value for value in evaluated if value is not None])
        if name == "round":
            if not evaluated:
                raise ExpressionEngineError("round requiere al menos 1 argumento")
            ndigits = int(evaluated[1]) if len(evaluated) > 1 else 0
            return round(float(evaluated[0]), ndigits)
        if name == "concat":
            return "".join("" if value is None else str(value) for value in evaluated)
        if name == "selected":
            if len(evaluated) != 2:
                raise ExpressionEngineError("selected requiere 2 argumentos")
            value, option = evaluated
            if isinstance(value, str):
                return str(option) in value.split()
            if isinstance(value, Iterable):
                return option in value
            return False
        if name == "true":
            return True
        if name == "false":
            return False
        if name == "today":
            return date.today().isoformat()
        if name == "now":
            return datetime.utcnow().isoformat()

        raise ExpressionEngineError(f"Funcion no soportada: {name}")

    def _flatten_numbers(self, values: list[Any]) -> list[float]:
        numbers: list[float] = []
        for value in values:
            if value is None:
                continue
            if isinstance(value, (int, float)):
                numbers.append(float(value))
            elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
                numbers.extend(self._flatten_numbers(list(value)))
        return numbers


expression_engine = ExpressionEngine()
