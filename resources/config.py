import os

from fastmcp import FastMCP

from models.response import GodotServerConfig

config_mcp = FastMCP(name="Config")


@config_mcp.resource("resource://config")
def get_config() -> dict:
    """Provide the application's configuration using environment variables."""

    return GodotServerConfig(
        godot_path=os.getenv("GODOT_PATH"),
        godot_operations_script=os.getenv("GODOT_OPERATIONS_SCRIPT"),
        debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
        godot_debug_mode=os.getenv("GODOT_DEBUG_MODE", "false").lower() == "true",
        strict_path_validation=os.getenv("STRICT_PATH_VALIDATION", "false").lower()
        == "true",
    ).model_dump(by_alias=True)
