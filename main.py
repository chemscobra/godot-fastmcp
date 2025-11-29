import asyncio
import sys

from fastmcp import FastMCP

from resources import config_mcp
from tools import godot_mcp

mcp = FastMCP(
    name="GodotEngineMCP",
    version="0.1.0",
    port=8000,
)


async def setup_server():
    await mcp.import_server(config_mcp)
    await mcp.import_server(godot_mcp)


if __name__ == "__main__":
    asyncio.run(setup_server())

    if "--http" in sys.argv:
        mcp.run(transport="http", port=8000)
    else:
        mcp.run()
