import os
from fastmcp import FastMCP


config_mcp = FastMCP(name="Godot MCP Config")


@config_mcp.resource("resource://config")
def get_config() -> dict:
    """Provide the application's configuration using environment variables."""
    return {
        "godot_path": os.getenv("GODOT_PATH"),
        "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
        "godot_debug_mode": os.getenv("GODOT_DEBUG_MODE", "false").lower() == "true",
        "strict_path_validation": os.getenv("STRICT_PATH_VALIDATION", "false").lower()
        == "true",
    }
