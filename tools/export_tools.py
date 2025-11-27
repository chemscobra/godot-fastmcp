from fastmcp import FastMCP

godot_mcp = FastMCP(name="GodotTools")


def register_export_tools(mcp: FastMCP):
    """Register the Export Tools"""

    @mcp.tool
    def export_mesh_library(
        project_path: str,
        scene_path: str,
        output_path: str,
        mesh_item_names: list = None,
    ) -> str:
        """Export meshes from a scene as a MeshLibrary resource."""
        raise NotImplementedError("export_mesh_library tool is not implemented yet.")
