"""Tool registry — auto-registers all available tools on import."""

from app.tools.base import register, get_tool, get_tool_catalog, list_tools
from app.tools.fines import check_plate_fines

# Register all tools
register(check_plate_fines)

__all__ = [
    "register",
    "get_tool",
    "get_tool_catalog",
    "list_tools",
    "check_plate_fines",
]
