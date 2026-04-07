"""
Tool calling infrastructure.

Public API:
    tool_registry   — catalogue of available tools
    tool_executor   — dispatches AI tool calls to implementations
    BaseTool        — base class for custom tools
    ToolResult      — result type returned by tool execution
"""

from app.ai.tools.base import BaseTool, ToolResult
from app.ai.tools.registry import tool_registry
from app.ai.tools.executor import tool_executor

__all__ = ["BaseTool", "ToolResult", "tool_registry", "tool_executor"]
