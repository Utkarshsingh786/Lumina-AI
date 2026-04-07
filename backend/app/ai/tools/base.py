"""
Tool base — defines the contract every tool must implement.

Why separate from providers/base.py:
- ToolDefinition (in providers/base.py) is the schema sent TO the AI.
- ToolResult (here) is the outcome returned FROM execution.
- BaseTool ties both together: it owns the schema and its own execution logic.

Adding a new tool = one new file + one line in registry.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Normalized result of a tool execution."""
    tool_name: str
    content: str          # Human-readable result sent back to the AI
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    Abstract base for all tools.

    Subclasses must set:
    - name: unique identifier (used in tool calls)
    - description: shown to the AI to decide when to use this tool
    - parameters_schema: JSON Schema object for the tool's arguments
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Run the tool with the given arguments and return a result."""
        ...

    def to_definition(self):
        """Convert to ToolDefinition for the provider layer."""
        from app.ai.providers.base import ToolDefinition
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )
