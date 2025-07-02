from fastmcp import FastMCP
import os
import subprocess
import json

godot_mcp = FastMCP(name="Godot MCP")


@godot_mcp.tool("get_godot_version")
def get_godot_version():
    """Return the version string of the Godot executable.

    Uses the GODOT_PATH environment variable if set, otherwise defaults to 'godot' in PATH.
    """
    godot_path = os.environ.get("GODOT_PATH", "godot")
    try:
        result = subprocess.run(
            [godot_path, "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {"content": [{"type": "text", "text": result.stdout.strip()}]}
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error running Godot: " + result.stderr.strip(),
                    }
                ],
                "isError": True,
            }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Failed to get Godot version: {e}"}],
            "isError": True,
        }


@godot_mcp.tool()
def create_scene(
    project_path: str, scene_path: str, root_node_type: str = "Node2D"
) -> str:
    """Create a new Godot scene at the specified path with the given root node type.

    The scene will be created inside the project located at 'project_path'.
    """
    params = {"scene_path": scene_path, "root_node_type": root_node_type}
    cmd = [
        "godot",
        "--headless",
        "--path",
        project_path,
        "--script",
        "scripts/godot_operations.gd",
        "create_scene",
        json.dumps(params),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return proc.stdout


@godot_mcp.tool()
def add_node(
    project_path: str,
    scene_path: str,
    node_type: str,
    node_name: str,
    parent_node_path: str = "root",
    properties: dict = None,
) -> str:
    """Add a node to an existing scene in Godot."""
    raise NotImplementedError("add_node tool is not implemented yet.")


@godot_mcp.tool()
def load_sprite(
    project_path: str,
    scene_path: str,
    node_path: str,
    texture_path: str,
) -> str:
    """Load a sprite texture into a Sprite2D, Sprite3D, or TextureRect node in a scene."""
    raise NotImplementedError("load_sprite tool is not implemented yet.")


@godot_mcp.tool()
def export_mesh_library(
    project_path: str,
    scene_path: str,
    output_path: str,
    mesh_item_names: list = None,
) -> str:
    """Export meshes from a scene as a MeshLibrary resource."""
    raise NotImplementedError("export_mesh_library tool is not implemented yet.")


@godot_mcp.tool()
def save_scene(
    project_path: str,
    scene_path: str,
    new_path: str = None,
) -> str:
    """Save changes to a scene file, optionally to a new path."""
    raise NotImplementedError("save_scene tool is not implemented yet.")


@godot_mcp.tool()
def get_uid(
    project_path: str,
    file_path: str,
) -> str:
    """Get the UID for a specific file (scene, script, or shader)."""
    raise NotImplementedError("get_uid tool is not implemented yet.")


@godot_mcp.tool()
def resave_resources(
    project_path: str,
) -> str:
    """Resave all resources in the project to update UID references and generate missing UIDs."""
    raise NotImplementedError("resave_resources tool is not implemented yet.")
