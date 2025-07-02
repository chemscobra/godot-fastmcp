from fastmcp import FastMCP
import asyncio
from src.godot_mcp.tools import godot_mcp
from src.godot_mcp.resources import config_mcp


main_mcp = FastMCP(
    name="Godot FastMCP",
    version="0.1.0",
    description="Godot MCP with FastMCP for managing Godot projects and scenes.",
)


async def setup_server():
    await main_mcp.import_server(config_mcp, prefix="config")
    await main_mcp.import_server(godot_mcp, prefix="godot")


if __name__ == "__main__":
    asyncio.run(setup_server())
    main_mcp.run()
