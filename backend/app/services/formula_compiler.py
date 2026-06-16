"""
Proyecto: InfoMatt360
Modulo: Formula Compiler v1
Responsabilidad: Convertir expresiones textuales en AST validable para el Expression Engine.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class FormulaCompilerError(Exception):
    """Error controlado de compilacion de formula."""


class TokenType(str, Enum):
    FIELD = "FIELD"
    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"


@dataclass(frozen=True)
class Token:
    token_type: TokenType
    value: str


@dataclass
class ASTNode:
    node_type: str
    value: str | float | None = None
    children: list["ASTNode"] = field(default_factory=list)


class FormulaCompiler:
    """Compilador de formulas para INFO-MATT.

    Alcance v1:
    - campos con sintaxis ${campo};
    - numeros;
    - cadenas simples entre comillas;
    - operadores aritmeticos y comparadores;
    - llamadas a funciones basicas tipo if(), sum(), count().
    """

    FIELD_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_\.\-]+)\}")
    OPERATORS = {"+", "-", "*", "/", "=", "!=", ">", "<", ">=", "<="}
    PRECEDENCE = {"=": 1, "!=": 1, ">": 1, "<": 1, ">=": 1, "<=": 1, "+": 2, "-": 2, "*": 3, "/": 3}
    NODE_BY_OPERATOR = {
        "+": "ADD",
        "-": "SUBTRACT",
        "*": "MULTIPLY",
        "/": "DIVIDE",
        "=": "EQUAL",
        "!=": "NOT_EQUAL",
        ">": "GREATER_THAN",
        "<": "LESS_THAN",
        ">=": "GREATER_EQUAL",
        "<=": "LESS_EQUAL",
    }
    ALLOWED_FUNCTIONS = {"if", "sum", "count", "round", "concat", "selected", "today", "now", "true", "false"}

    def tokenize(self, expression: str) -> list[Token]:
        """Convierte texto de expresion en tokens."""
        if not expression or not expression.strip():
            raise FormulaCompilerError("La expresion esta vacia")

        tokens: list[Token] = []
        index = 0
        while index < len(expression):
            char = expression[index]
            if char.isspace():
                index += 1
                continue

            if expression.startswith("${", index):
                end = expression.find("}", index + 2)
                if end == -1:
                    raise FormulaCompilerError("Referencia de campo sin cierre }")
                field_name = expression[index + 2 : end]
                if not field_name:
                    raise FormulaCompilerError("Referencia de campo vacia")
                tokens.append(Token(TokenType.FIELD, field_name))
                index = end + 1
                continue

            if char.isdigit():
                start = index
                while index < len(expression) and (expression[index].isdigit() or expression[index] == "."):
                    index += 1
                tokens.append(Token(TokenType.NUMBER, expression[start:index]))
                continue

            if char in {"'", '"'}:
                quote = char
                index += 1
                start = index
                while index < len(expression) and expression[index] != quote:
                    index += 1
                if index >= len(expression):
                    raise FormulaCompilerError("Cadena sin cierre")
                tokens.append(Token(TokenType.STRING, expression[start:index]))
                index += 1
                continue

            two_char = expression[index : index + 2]
            if two_char in {"!=", ">=", "<="}:
                tokens.append(Token(TokenType.OPERATOR, two_char))
                index += 2
                continue

            if char in {"+", "-", "*", "/", "=", ">", "<"}:
                tokens.append(Token(TokenType.OPERATOR, char))
                index += 1
                continue

            if char == "(":
                tokens.append(Token(TokenType.LPAREN, char))
                index += 1
                continue

            if char == ")":
                tokens.append(Token(TokenType.RPAREN, char))
                index += 1
                continue

            if char == ",":
                tokens.append(Token(TokenType.COMMA, char))
                index += 1
                continue

            if char.isalpha() or char == "_":
                start = index
                while index < len(expression) and (expression[index].isalnum() or expression[index] == "_"):
                    index += 1
                tokens.append(Token(TokenType.IDENTIFIER, expression[start:index]))
                continue

            raise FormulaCompilerError(f"Token no reconocido: {char}")

        return tokens

    def extract_references(self, expression: str) -> list[str]:
        """Extrae referencias ${campo} para integracion con Dependency Graph."""
        return sorted(set(self.FIELD_PATTERN.findall(expression or "")))

    def validate_expression(self, expression: str, known_fields: set[str] | None = None) -> None:
        """Valida estructura basica y campos conocidos."""
        tokens = self.tokenize(expression)
        balance = 0
        for token in tokens:
            if token.token_type == TokenType.LPAREN:
                balance += 1
            elif token.token_type == TokenType.RPAREN:
                balance -= 1
            if balance < 0:
                raise FormulaCompilerError("Parentesis desbalanceados")
            if token.token_type == TokenType.FIELD and known_fields is not None and token.value not in known_fields:
                raise FormulaCompilerError(f"Campo inexistente: {token.value}")
            if token.token_type == TokenType.IDENTIFIER and token.value not in self.ALLOWED_FUNCTIONS:
                raise FormulaCompilerError(f"Funcion desconocida: {token.value}")
        if balance != 0:
            raise FormulaCompilerError("Parentesis desbalanceados")

    def build_ast(self, expression: str, known_fields: set[str] | None = None) -> ASTNode:
        """Construye AST desde expresion textual."""
        self.validate_expression(expression, known_fields)
        return self.parse(self.tokenize(expression))

    def parse(self, tokens: list[Token]) -> ASTNode:
        """Parser Pratt simplificado para expresiones binarias y funciones."""
        self._tokens = tokens
        self._position = 0
        ast = self._parse_expression(0)
        if self._position != len(self._tokens):
            raise FormulaCompilerError("Expresion invalida")
        return ast

    def _parse_expression(self, min_precedence: int) -> ASTNode:
        left = self._parse_primary()
        while self._position < len(self._tokens):
            token = self._tokens[self._position]
            if token.token_type != TokenType.OPERATOR:
                break
            precedence = self.PRECEDENCE[token.value]
            if precedence < min_precedence:
                break
            self._position += 1
            right = self._parse_expression(precedence + 1)
            left = ASTNode(self.NODE_BY_OPERATOR[token.value], children=[left, right])
        return left

    def _parse_primary(self) -> ASTNode:
        if self._position >= len(self._tokens):
            raise FormulaCompilerError("Expresion incompleta")
        token = self._tokens[self._position]
        self._position += 1

        if token.token_type == TokenType.FIELD:
            return ASTNode("FIELD", token.value)
        if token.token_type == TokenType.NUMBER:
            return ASTNode("NUMBER", float(token.value))
        if token.token_type == TokenType.STRING:
            return ASTNode("STRING", token.value)
        if token.token_type == TokenType.IDENTIFIER:
            if self._position < len(self._tokens) and self._tokens[self._position].token_type == TokenType.LPAREN:
                return self._parse_function_call(token.value)
            return ASTNode("IDENTIFIER", token.value)
        if token.token_type == TokenType.LPAREN:
            node = self._parse_expression(0)
            if self._position >= len(self._tokens) or self._tokens[self._position].token_type != TokenType.RPAREN:
                raise FormulaCompilerError("Parentesis desbalanceados")
            self._position += 1
            return node

        raise FormulaCompilerError(f"Token inesperado: {token.value}")

    def _parse_function_call(self, function_name: str) -> ASTNode:
        self._position += 1  # consume LPAREN
        args: list[ASTNode] = []
        if self._position < len(self._tokens) and self._tokens[self._position].token_type == TokenType.RPAREN:
            self._position += 1
            return ASTNode("FUNCTION", function_name, args)

        while True:
            args.append(self._parse_expression(0))
            if self._position >= len(self._tokens):
                raise FormulaCompilerError("Funcion sin cierre )")
            if self._tokens[self._position].token_type == TokenType.COMMA:
                self._position += 1
                continue
            if self._tokens[self._position].token_type == TokenType.RPAREN:
                self._position += 1
                break
            raise FormulaCompilerError("Separador de funcion invalido")
        return ASTNode("FUNCTION", function_name, args)


formula_compiler = FormulaCompiler()
