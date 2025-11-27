from fastmcp import FastMCP

from .export_tools import register_export_tools
from .get_version import register_get_version
from .project_tools import register_project_tools
from .scene_tools import register_scene_tools

godot_mcp = FastMCP(name="GodotTools")


def register_all_tools(mcp: FastMCP):
    """Register all Godot-related tools to the given MCP instance."""
    register_get_version(mcp)
    register_project_tools(mcp)
    register_scene_tools(mcp)
    register_export_tools(mcp)


register_all_tools(godot_mcp)
