import json
import os
import subprocess

from fastmcp import FastMCP

from models.response import ContentItem, ToolResponse

godot_mcp = FastMCP(name="GodotTools")


def register_export_tools(mcp: FastMCP):
    """Register the Export Tools"""

    @mcp.tool
    def export_mesh_library(
        project_path: str,
        scene_path: str,
        output_path: str,
        mesh_item_names: list | None = None,
    ):
        """Export meshes from a scene as a MeshLibrary resource."""
        if not project_path or not scene_path or not output_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="project_path, scene_path, and output_path are required.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path or ".." in scene_path or ".." in output_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text", text="Invalid path: path traversal is not allowed."
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        project_file = os.path.join(project_path, "project.godot")
        if not os.path.exists(project_file):
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Not a valid Godot project: {project_path}. Missing project.godot."
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        godot_path = os.environ.get("GODOT_PATH", "godot")
        operations_script = os.environ.get(
            "GODOT_OPERATIONS_SCRIPT", "gd_scripts/godot_operations.gd"
        )

        params: dict[str, object] = {
            "scene_path": scene_path,
            "output_path": output_path,
        }
        if mesh_item_names:
            params["mesh_item_names"] = mesh_item_names

        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "export_mesh_library",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception as e:
            resp = ToolResponse(
                content=[ContentItem(type="text", text=f"Failed to run Godot: {e}")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        stdout_text = proc.stdout.strip() if proc.stdout else ""
        stderr_text = proc.stderr.strip() if proc.stderr else ""

        if proc.returncode != 0:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to export MeshLibrary: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the scene exists and contains MeshInstance3D nodes\n"
                            "- Ensure the output path is writable\n"
                            "- Verify the Godot operations script path\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        resp = ToolResponse(
            content=[
                ContentItem(
                    type="text",
                    text=stdout_text or "MeshLibrary exported successfully.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)
