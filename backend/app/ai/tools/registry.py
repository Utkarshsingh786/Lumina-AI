"""
Tool registry — central catalogue of all available tools.

Why a registry:
- Single place to enable/disable tools without touching ChatService
- Tools are registered at module load time; no circular imports
- Exposes the ToolDefinition list that gets passed to the AI provider

Usage:
    from app.ai.tools.registry import tool_registry

    defs = tool_registry.get_tool_definitions()   # pass to provider
    tool = tool_registry.get("calculator")          # for execution
"""

from app.ai.providers.base import ToolDefinition
from app.ai.tools.base import BaseTool
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            logger.warning("tool_registry.duplicate", tool_name=tool.name)
        self._tools[tool.name] = tool
        logger.debug("tool_registry.registered", tool_name=tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Return all registered tools as ToolDefinition objects for the AI provider."""
        return [t.to_definition() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)


# Module-level singleton — import this everywhere
tool_registry = ToolRegistry()

# Register all built-in tools
from app.ai.tools.calculator import CalculatorTool  # noqa: E402
from app.ai.tools.weather import WeatherTool          # noqa: E402
from app.ai.tools.web_search import WebSearchTool     # noqa: E402

tool_registry.register(CalculatorTool())
tool_registry.register(WeatherTool())
tool_registry.register(WebSearchTool())
