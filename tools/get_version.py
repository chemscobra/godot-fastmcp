import os
import subprocess

from models.response import ContentItem, ToolResponse


def register_get_version(mcp):
    """Register the get_version tool"""

    @mcp.tool
    def get_version():
        """Return the version string of the Godot executable."""
        godot_path = os.environ.get("GODOT_PATH", "godot")
        try:
            result = subprocess.run(
                [godot_path, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                resp = ToolResponse(
                    content=[ContentItem(type="text", text=result.stdout.strip())]
                )
                return resp.model_dump(by_alias=True)
            else:
                resp = ToolResponse(
                    content=[
                        ContentItem(
                            type="text",
                            text="Error running Godot: " + result.stderr.strip(),
                        )
                    ],
                    is_error=True,
                )
                return resp.model_dump(by_alias=True)
        except Exception as e:
            resp = ToolResponse(
                content=[
                    ContentItem(type="text", text=f"Failed to get Godot version: {e}")
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)
