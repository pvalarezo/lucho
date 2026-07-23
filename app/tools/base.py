"""Tool system — pluggable external actions (API calls, MCP tools).

Architecture principle (spec §5): tools are CALLED BY CODE, never decided by LLM.
The flow is:
1. Router (LLM) → identifies tool intent (e.g., "check_fines")
2. Extractor (LLM) → extracts parameters (plate number)
3. Tool executor (CODE) → calls the external API
4. Response formatter (LLM) → explains result to user

This keeps LLM in the edges and determinism in the center.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    rendered: str | None = None  # human-readable summary


class Tool(ABC):
    """Abstract base for external tools (API calls, MCP servers, etc.)."""

    name: str
    description: str  # for the LLM to understand when to use this tool
    parameters: dict  # JSON Schema for parameters

    @abstractmethod
    async def execute(self, params: dict, user_id: str | None = None) -> ToolResult:
        """Execute the tool with given parameters. Must be implemented by subclasses."""


# ---- Tool registry ----

_registry: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    """Register a tool in the global registry."""
    _registry[tool.name] = tool
    logger.info("Registered tool: %s — %s", tool.name, tool.description)


def get_tool(name: str) -> Tool | None:
    """Get a registered tool by name."""
    return _registry.get(name)


def get_tool_catalog() -> list[dict]:
    """
    Return a catalog of all registered tools for the LLM router.
    Used in the router prompt so the LLM knows what's available.
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in _registry.values()
    ]


def list_tools() -> list[str]:
    """List all registered tool names."""
    return list(_registry.keys())
