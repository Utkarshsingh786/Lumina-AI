"""
Tool executor — dispatches tool calls from the AI to the correct tool.

Responsibilities:
- Validate that the requested tool exists
- Parse and validate JSON arguments
- Execute the tool and return a ToolResult
- Catch all exceptions so a bad tool never kills the chat stream

Usage:
    result = await tool_executor.execute("calculator", {"expression": "2+2"})
"""

import json
from typing import Any

from app.ai.tools.base import ToolResult
from app.ai.tools.registry import tool_registry
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    async def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """
        Execute a named tool with the given arguments.
        Always returns a ToolResult — never raises. Failures are surfaced
        as ToolResult(is_error=True) so the AI can report them to the user.
        """
        tool = tool_registry.get(tool_name)
        if tool is None:
            logger.warning("tool_executor.unknown_tool", tool_name=tool_name)
            return ToolResult(
                tool_name=tool_name,
                content=f"Tool '{tool_name}' is not available.",
                is_error=True,
            )

        logger.info("tool_executor.execute", tool_name=tool_name, args=args)

        try:
            result = await tool.execute(args)
            logger.info(
                "tool_executor.result",
                tool_name=tool_name,
                is_error=result.is_error,
                content_length=len(result.content),
            )
            return result
        except Exception as e:
            logger.error(
                "tool_executor.unexpected_error",
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return ToolResult(
                tool_name=tool_name,
                content=f"Tool '{tool_name}' encountered an unexpected error: {e}",
                is_error=True,
            )

    async def execute_from_call(self, tool_call: dict) -> ToolResult:
        """
        Execute from a raw tool_call dict as returned by the AI provider.
        Handles JSON argument parsing.
        """
        tool_name = tool_call.get("name", "")
        raw_args = tool_call.get("arguments", "{}")

        try:
            args: dict[str, Any] = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError as e:
            return ToolResult(
                tool_name=tool_name,
                content=f"Invalid arguments JSON for tool '{tool_name}': {e}",
                is_error=True,
            )

        return await self.execute(tool_name, args)


# Module-level singleton
tool_executor = ToolExecutor()
