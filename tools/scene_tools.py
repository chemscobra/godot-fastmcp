import json
import os
import subprocess

from fastmcp import FastMCP

from models.response import ContentItem, ToolResponse


def register_scene_tools(mcp: FastMCP):
    """Register the Scene Tools"""

    @mcp.tool
    def create_scene(
        project_path: str, scene_path: str, root_node_type: str = "Node2D"
    ):
        """Create a new Godot scene at the specified path with the given root node type.

        The scene will be created inside the project located at 'project_path'.
        Returns: ToolResponse.model_dump(by_alias=True)
        """

        if not project_path or not scene_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text", text="project_path and scene_path are required."
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path or ".." in scene_path:
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
                        text=f"Not a valid Godot project: {project_path}. Missing project.godot.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        godot_path = os.environ.get("GODOT_PATH", "godot")
        operations_script = os.environ.get(
            "GODOT_OPERATIONS_SCRIPT", "gd_scripts/godot_operations.gd"
        )

        params = {"scene_path": scene_path, "root_node_type": root_node_type}
        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "create_scene",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as e:
            resp = ToolResponse(
                content=[ContentItem(type="text", text=f"Failed to run Godot: {e}")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if proc.returncode != 0:
            # Mirror TS handler's helpful suggestions
            stderr_text = proc.stderr.strip() if proc.stderr else "Unknown error"
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to create scene: {stderr_text}\n\n"
                            "Suggestions:\n"
                            "- Ensure the root node type is valid\n"
                            "- Ensure you have write permissions to the scene path\n"
                            "- Verify the scene path is valid\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        stdout_text = proc.stdout.strip() if proc.stdout else ""
        resp = ToolResponse(
            content=[
                ContentItem(
                    type="text",
                    text=f"Scene created successfully at: {scene_path}\n\nOutput:\n{stdout_text}",
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def save_scene(
        project_path: str,
        scene_path: str,
        new_path: str | None = None,
    ):
        """Save changes to a scene file, optionally to a new path."""
        if not project_path or not scene_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="project_path and scene_path are required.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if (
            ".." in project_path
            or ".." in scene_path
            or (new_path and ".." in new_path)
        ):
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

        params = {"scene_path": scene_path}
        if new_path:
            params["new_path"] = new_path

        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "save_scene",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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
                            f"Failed to save scene: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the scene exists and is valid\n"
                            "- Ensure the target path is writable\n"
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
                    text=stdout_text or "Scene saved successfully.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def load_sprite(
        project_path: str,
        scene_path: str,
        node_path: str,
        texture_path: str,
    ):
        """Load a sprite texture into a Sprite2D, Sprite3D, or TextureRect node in a scene."""
        if not project_path or not scene_path or not node_path or not texture_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            "project_path, scene_path, node_path, and texture_path are required."
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if (
            ".." in project_path
            or ".." in scene_path
            or ".." in node_path
            or ".." in texture_path
        ):
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

        params = {
            "scene_path": scene_path,
            "node_path": node_path,
            "texture_path": texture_path,
        }

        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "load_sprite",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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
                            f"Failed to load sprite: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the scene and texture paths exist\n"
                            "- Ensure the node path points to a Sprite2D, Sprite3D, or TextureRect\n"
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
                    text=stdout_text or "Sprite loaded successfully.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def add_node(
        project_path: str,
        scene_path: str,
        node_type: str,
        node_name: str,
        parent_node_path: str = "root",
        properties: dict | None = None,
    ):
        """Add a node to an existing scene in Godot."""
        if not project_path or not scene_path or not node_type or not node_name:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="project_path, scene_path, node_type, and node_name are required.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path or ".." in scene_path or ".." in node_name:
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
            "node_type": node_type,
            "node_name": node_name,
            "parent_node_path": parent_node_path,
        }

        if properties is not None:
            params["properties"] = properties

        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "add_node",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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
                            f"Failed to add node: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the node type exists and can be instantiated\n"
                            "- Ensure the scene exists and is valid\n"
                            "- Check parent node path if provided\n"
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
                    text=stdout_text or "Node added successfully.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)
