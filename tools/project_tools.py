import json
import os
import subprocess

from fastmcp import FastMCP

from models.response import ContentItem, ToolResponse


def register_project_tools(mcp: FastMCP):
    """Register the Project Tools"""

    @mcp.tool
    def launch_editor(project_path: str):
        """Launch the Godot editor for a specific project.

        Opens the Godot editor in edit mode (-e flag) for the project at the given path.
        The editor runs asynchronously and does not wait for it to close.
        """
        if not project_path:
            resp = ToolResponse(
                content=[ContentItem(type="text", text="Project path is required.")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid project path: path traversal is not allowed.",
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
                            f"Not a valid Godot project: {project_path}\n\n"
                            "Suggestions:\n"
                            "- Ensure the path points to a directory containing a project.godot file\n"
                            "- Use list_projects to find valid Godot projects\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        godot_path = os.environ.get("GODOT_PATH", "godot")

        try:
            # Launch the editor with -e flag (edit mode) and --path to specify the project
            subprocess.Popen(
                [godot_path, "-e", "--path", project_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print(f"Launched Godot editor for project at {project_path}")

            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=f"Godot editor launched successfully for project at {project_path}.",
                    )
                ]
            )
            return resp.model_dump(by_alias=True)
        except Exception as e:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to launch Godot editor: {e}\n\n"
                            "Suggestions:\n"
                            "- Ensure Godot is installed correctly\n"
                            "- Check if the GODOT_PATH environment variable is set correctly\n"
                            "- Verify the project path is accessible\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

    @mcp.tool
    def list_projects(directory: str, recursive: bool = False):
        """List Godot projects in a directory.

        Searches for directories containing a project.godot file.
        Can search recursively through subdirectories.
        """
        if not directory:
            resp = ToolResponse(
                content=[ContentItem(type="text", text="Directory is required.")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in directory:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid directory path: path traversal is not allowed.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if not os.path.exists(directory):
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=f"Directory does not exist: {directory}\n\n"
                        "Suggestions:\n"
                        "- Provide a valid directory path that exists on the system\n",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        try:
            projects = []

            # Check if the directory itself is a Godot project
            project_file = os.path.join(directory, "project.godot")
            if os.path.exists(project_file):
                projects.append(
                    {
                        "path": directory,
                        "name": os.path.basename(directory),
                    }
                )

            # If not recursive, only check immediate subdirectories
            if not recursive:
                try:
                    entries = os.listdir(directory)
                    for entry in entries:
                        subdir = os.path.join(directory, entry)
                        if os.path.isdir(subdir):
                            project_file = os.path.join(subdir, "project.godot")
                            if os.path.exists(project_file):
                                projects.append(
                                    {
                                        "path": subdir,
                                        "name": entry,
                                    }
                                )
                except OSError as e:
                    resp = ToolResponse(
                        content=[
                            ContentItem(
                                type="text",
                                text=(
                                    f"Failed to list projects: {e}\n\n"
                                    "Suggestions:\n"
                                    "- Ensure the directory exists and is accessible\n"
                                    "- Check if you have permission to read the directory\n"
                                ),
                            )
                        ],
                        is_error=True,
                    )
                    return resp.model_dump(by_alias=True)
            else:
                # Recursive search
                def find_projects_recursive(current_dir):
                    found = []
                    try:
                        entries = os.listdir(current_dir)
                        for entry in entries:
                            # Skip hidden directories
                            if entry.startswith("."):
                                continue

                            subdir = os.path.join(current_dir, entry)
                            if os.path.isdir(subdir):
                                # Check if this directory is a Godot project
                                project_file = os.path.join(subdir, "project.godot")
                                if os.path.exists(project_file):
                                    found.append(
                                        {
                                            "path": subdir,
                                            "name": entry,
                                        }
                                    )
                                else:
                                    # Recursively search this directory
                                    found.extend(find_projects_recursive(subdir))
                    except OSError:
                        # Skip directories that can't be read
                        pass
                    return found

                projects.extend(find_projects_recursive(directory))

            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=json.dumps(projects, indent=2),
                    )
                ]
            )
            return resp.model_dump(by_alias=True)

        except Exception as e:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to list projects: {e}\n\n"
                            "Suggestions:\n"
                            "- Ensure the directory exists and is accessible\n"
                            "- Check if you have permission to read the directory\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

    @mcp.tool
    def get_uid(
        project_path: str,
        file_path: str,
    ) -> str:
        """Get the UID for a specific file (scene, script, or shader)."""
        raise NotImplementedError("get_uid tool is not implemented yet.")

    @mcp.tool
    def resave_resources(
        project_path: str,
    ) -> str:
        """Resave all resources in the project to update UID references and generate missing UIDs."""
        raise NotImplementedError("resave_resources tool is not implemented yet.")
