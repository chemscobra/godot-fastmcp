import asyncio

from fastmcp import Client

client = Client("http://127.0.0.1:8000/mcp")


async def call_tool():
    async with client:
        result = await client.call_tool(
            # "get_project_info",
            # "get_project_structure",
            "launch_editor",
            {"project_path": "/home/godotmentor/Projects/improving_gj_2025"},
        )
        print(result)


asyncio.run(call_tool())
