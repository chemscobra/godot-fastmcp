from fastmcp import FastMCP
import asyncio
from godot_mcp.tools import godot_mcp
from godot_mcp.resources import config_mcp


main_mcp = FastMCP(
    name="Godot FastMCP",
    version="0.1.0",
)


async def setup_server():
    await main_mcp.import_server(config_mcp, prefix="config")
    await main_mcp.import_server(godot_mcp, prefix="godot")


def run_server():
    """Run the FastMCP server."""
    asyncio.run(setup_server())
    main_mcp.run()


if __name__ == "__main__":
    run_server()
