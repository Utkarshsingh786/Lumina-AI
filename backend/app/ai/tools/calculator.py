"""
Calculator tool — safe mathematical expression evaluator.

Uses Python's ast module to parse and evaluate expressions without
exec/eval, preventing code injection. Supports arithmetic, powers,
and basic math functions (sqrt, abs, round, floor, ceil, log).
"""

import ast
import math
import operator
from typing import Any

from app.ai.tools.base import BaseTool, ToolResult
from app.core.logging import get_logger

logger = get_logger(__name__)

# Whitelist of safe operators
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Whitelist of safe functions
_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate an AST node using only whitelisted operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, int):
            return node.value          # keep as int so round(x, 2) works
        if isinstance(node.value, float):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            return _SAFE_FUNCTIONS[node.id]  # type: ignore[return-value]
        raise ValueError(f"Unknown name: {node.id!r}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _OPERATORS[op_type](left, right)  # type: ignore[operator]

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return _OPERATORS[op_type](operand)  # type: ignore[operator]

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCTIONS:
            raise ValueError(f"Unknown function: {func_name!r}")
        func = _SAFE_FUNCTIONS[func_name]
        args = [_safe_eval(arg) for arg in node.args]
        return func(*args)  # type: ignore[operator]

    raise ValueError(f"Unsupported AST node type: {type(node).__name__}")


def evaluate_expression(expression: str) -> str:
    """Parse and evaluate a math expression. Returns the result as a string."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}") from e

    result = _safe_eval(tree)

    # Format nicely: drop trailing .0 for whole numbers
    if isinstance(result, int):
        return str(result)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(round(result, 10))


class CalculatorTool(BaseTool):
    name = "calculator"
    description = (
        "Evaluate mathematical expressions. Supports arithmetic (+, -, *, /, **, %), "
        "and functions: sqrt, abs, round, floor, ceil, log, log10, log2, sin, cos, tan. "
        "Constants: pi, e. Use this for any numeric calculation."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "The mathematical expression to evaluate. "
                    "Examples: '2 + 2', 'sqrt(144)', '(15 * 8) / 4', '2**10'"
                ),
            }
        },
        "required": ["expression"],
    }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        expression = args.get("expression", "").strip()
        if not expression:
            return ToolResult(
                tool_name=self.name,
                content="Error: no expression provided",
                is_error=True,
            )

        logger.debug("calculator.execute", expression=expression)
        try:
            result = evaluate_expression(expression)
            return ToolResult(
                tool_name=self.name,
                content=f"{expression} = {result}",
                metadata={"expression": expression, "result": result},
            )
        except (ValueError, ZeroDivisionError, OverflowError) as e:
            return ToolResult(
                tool_name=self.name,
                content=f"Error evaluating '{expression}': {e}",
                is_error=True,
            )
