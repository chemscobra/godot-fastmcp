import json
import os
import re
import subprocess
import threading
from pathlib import Path

from fastmcp import FastMCP

from models.response import ContentItem, ToolResponse


class ActiveProcessInfo:
    def __init__(
        self,
        process: subprocess.Popen,
        output: list[str],
        errors: list[str],
        output_lock: threading.Lock,
        error_lock: threading.Lock,
    ):
        self.process = process
        self.output = output
        self.errors = errors
        self.output_lock = output_lock
        self.error_lock = error_lock


_active_process: ActiveProcessInfo | None = None
_active_process_lock = threading.Lock()


def _capture_stream(stream, buffer: list[str], buffer_lock: threading.Lock):
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            with buffer_lock:
                buffer.append(line.rstrip("\n"))
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _stop_active_process():
    global _active_process
    with _active_process_lock:
        active = _active_process
        _active_process = None

    if not active:
        return None

    proc = active.process
    if isinstance(proc, subprocess.Popen):
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass

    return active


def _build_tree(path: Path, max_depth: int = -1):
    """
    Recursively build a nested dict structure of directories and files.
    If max_depth >=0, limit recursion beyond that depth.
    """
    tree = {"name": path.name, "path": str(path), "type": "directory", "children": []}
    if max_depth == 0:
        return tree
    try:
        for entry in sorted(path.iterdir()):
            if entry.name.startswith("."):
                continue  # skip hidden
            if entry.is_dir():
                subtree = _build_tree(entry, max_depth - 1 if max_depth > 0 else -1)
                tree["children"].append(subtree)
            else:
                tree["children"].append(
                    {"name": entry.name, "path": str(entry), "type": "file"}
                )
    except Exception:
        # you might want to log or skip
        pass
    return tree


def _compute_project_structure_counts(project_path: str) -> dict:
    """
    Mirrors getProjectStructureAsync from index.ts:
    Recursively walk the project and count scenes, scripts, assets, and other files.
    - scenes: .tscn
    - scripts: .gd, .gdscript, .cs
    - assets: png, jpg, jpeg, webp, svg, ttf, wav, mp3, ogg
    - other: everything else
    """
    structure = {
        "scenes": 0,
        "scripts": 0,
        "assets": 0,
        "other": 0,
    }

    for root, dirs, files in os.walk(project_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:
            # Skip hidden files
            if filename.startswith("."):
                continue

            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

            if ext == "tscn":
                structure["scenes"] += 1
            elif ext in ("gd", "gdscript", "cs"):
                structure["scripts"] += 1
            elif ext in (
                "png",
                "jpg",
                "jpeg",
                "webp",
                "svg",
                "ttf",
                "wav",
                "mp3",
                "ogg",
            ):
                structure["assets"] += 1
            else:
                structure["other"] += 1

    return structure


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
    def run_project(project_path: str, scene: str | None = None):
        """Run the Godot project and capture output."""
        if not project_path:
            resp = ToolResponse(
                content=[ContentItem(type="text", text="Project path is required.")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path or (scene and ".." in scene):
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid project or scene path: path traversal is not allowed.",
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

        _stop_active_process()

        godot_path = os.environ.get("GODOT_PATH", "godot")
        cmd = [godot_path, "-d", "--path", project_path]
        if scene:
            cmd.append(scene)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to start Godot project: {e}\n\n"
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

        output: list[str] = []
        errors: list[str] = []
        output_lock = threading.Lock()
        error_lock = threading.Lock()

        if proc.stdout:
            threading.Thread(
                target=_capture_stream,
                args=(proc.stdout, output, output_lock),
                daemon=True,
            ).start()
        if proc.stderr:
            threading.Thread(
                target=_capture_stream,
                args=(proc.stderr, errors, error_lock),
                daemon=True,
            ).start()

        with _active_process_lock:
            global _active_process
            _active_process = ActiveProcessInfo(
                process=proc,
                output=output,
                errors=errors,
                output_lock=output_lock,
                error_lock=error_lock,
            )

        resp = ToolResponse(
            content=[
                ContentItem(
                    type="text",
                    text=(
                        "Godot project started in debug mode. "
                        "Use get_debug_output to fetch runtime output."
                    ),
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def get_debug_output():
        """Get the current debug output and errors from the active process."""
        with _active_process_lock:
            active = _active_process

        if not active:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            "No active Godot process.\n\n"
                            "Suggestions:\n"
                            "- Use run_project to start a project\n"
                            "- Ensure the project did not exit unexpectedly\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        output_lock = active.output_lock
        error_lock = active.error_lock
        output = active.output
        errors = active.errors

        with output_lock:
            output_snapshot = list(output)

        with error_lock:
            error_snapshot = list(errors)

        payload = {
            "output": output_snapshot,
            "errors": error_snapshot,
        }

        resp = ToolResponse(
            content=[
                ContentItem(
                    type="text",
                    text=json.dumps(payload, indent=2),
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def stop_project():
        """Stop the currently running Godot project."""
        active = _stop_active_process()
        if not active:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            "No active Godot process to stop.\n\n"
                            "Suggestions:\n"
                            "- Use run_project to start a project\n"
                            "- The process may have already terminated\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        output = active.output
        errors = active.errors
        output_lock = active.output_lock
        error_lock = active.error_lock

        with output_lock:
            output_snapshot = list(output)

        with error_lock:
            error_snapshot = list(errors)

        payload = {
            "message": "Godot project stopped",
            "finalOutput": output_snapshot,
            "finalErrors": error_snapshot,
        }

        resp = ToolResponse(
            content=[
                ContentItem(
                    type="text",
                    text=json.dumps(payload, indent=2),
                )
            ]
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
    ):
        """Get the UID for a specific file (scene, script, or shader)."""
        if not project_path or not file_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="project_path and file_path are required.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        if ".." in project_path or ".." in file_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid path: path traversal is not allowed.",
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
        operations_script = os.environ.get(
            "GODOT_OPERATIONS_SCRIPT", "gd_scripts/godot_operations.gd"
        )

        params = {"file_path": file_path}
        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "get_uid",
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

        stdout_text = proc.stdout.strip() if proc.stdout else ""
        stderr_text = proc.stderr.strip() if proc.stderr else ""

        if proc.returncode != 0:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Failed to get UID: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the file exists inside the project\n"
                            "- Check that GODOT_PATH and GODOT_OPERATIONS_SCRIPT are set correctly\n"
                            "- Use resave_resources to generate missing UIDs\n"
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
                    text=stdout_text or "UID lookup completed.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def resave_resources(
        project_path: str,
    ):
        """Resave all resources in the project to update UID references and generate missing UIDs."""
        return _update_project_uids(project_path)

    @mcp.tool
    def update_project_uids(
        project_path: str,
    ):
        """Update UID references in a Godot project by resaving resources."""
        return _update_project_uids(project_path)

    def _update_project_uids(project_path: str):
        if not project_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="project_path is required.",
                    )
                ],
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
        operations_script = os.environ.get(
            "GODOT_OPERATIONS_SCRIPT", "gd_scripts/godot_operations.gd"
        )

        params = {"project_path": project_path}
        cmd = [
            godot_path,
            "--headless",
            "--path",
            project_path,
            "--script",
            operations_script,
            "resave_resources",
            json.dumps(params),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
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
                            f"Failed to resave resources: {stderr_text or 'Unknown error'}\n\n"
                            "Suggestions:\n"
                            "- Ensure the project is accessible and writable\n"
                            "- Check that GODOT_PATH and GODOT_OPERATIONS_SCRIPT are set correctly\n"
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
                    text=stdout_text or "Resave operation completed.",
                )
            ]
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def get_project_structure(project_path: str, max_depth: int = -1):
        """Return the directory tree structure starting from `project_path`."""
        if not project_path:
            resp = ToolResponse(
                content=[ContentItem(type="text", text="Directory path is required.")],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        # Simple path-traversal guard; you may tighten this
        if ".." in project_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid directory path: path traversal not allowed.",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        root = Path(project_path)
        if not root.exists():
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text", text=f"Directory does not exist: {project_path}"
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        tree = _build_tree(root, max_depth=max_depth)
        resp = ToolResponse(
            content=[ContentItem(type="json", text=json.dumps(tree, indent=2))],
        )
        return resp.model_dump(by_alias=True)

    @mcp.tool
    def get_project_info(project_path: str):
        """
        Get high-level info about a Godot project, similar to handleGetProjectInfo in index.ts.

        Returns JSON text with:
        - name: project name (from config/name in project.godot if available, otherwise directory name)
        - path: project path
        - godotVersion: output of `godot --version`
        - structure: counts of scenes, scripts, assets, other
        """
        # Basic validation
        if not project_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Project path is required.\n\nSuggestions:\n"
                        "- Provide a valid path to a Godot project directory\n",
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        # Rough equivalent of validatePath in your TS (block "..")
        if ".." in project_path:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text="Invalid project path.\n\nSuggestions:\n"
                        "- Provide a valid path without '..' or other potentially unsafe characters\n",
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

        # Detect / choose Godot path – mirrors your this.godotPath + detectGodotPath idea
        godot_path = os.environ.get("GODOT_PATH", "godot")

        try:
            # Get Godot version (like `"${this.godotPath}" --version`)
            result = subprocess.run(
                [godot_path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip() or "Failed to get Godot version"
                )

            godot_version = result.stdout.strip()
        except Exception as e:
            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=(
                            f"Could not find a valid Godot executable path or failed to run Godot: {e}\n\n"
                            "Suggestions:\n"
                            "- Ensure Godot is installed correctly\n"
                            "- Set GODOT_PATH environment variable to specify the correct path\n"
                        ),
                    )
                ],
                is_error=True,
            )
            return resp.model_dump(by_alias=True)

        try:
            # Get project structure counts (async version in TS)
            project_structure = _compute_project_structure_counts(project_path)

            # Default project name is the directory name
            project_name = os.path.basename(os.path.normpath(project_path))

            # Try to extract config/name from project.godot, like the TS regex:
            # const configNameMatch = projectFileContent.match(/config\/name="([^"]+)"/);
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.search(r'config/name="([^"]+)"', content)
                if match and match.group(1):
                    project_name = match.group(1)
            except Exception:
                # If reading or regex fails, we just keep the directory name
                pass

            payload = {
                "name": project_name,
                "path": project_path,
                "godotVersion": godot_version,
                "structure": project_structure,
            }

            resp = ToolResponse(
                content=[
                    ContentItem(
                        type="text",
                        text=json.dumps(payload, indent=2),
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
                            f"Failed to get project info: {e}\n\n"
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
