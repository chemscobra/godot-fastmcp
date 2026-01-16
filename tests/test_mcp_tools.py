import json
import os
import subprocess
import tempfile
import time
from logging import getLogger
from pathlib import Path

import psutil
import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult

logger = getLogger(__name__)

# Configuration
TEST_PROJECT_PATH = os.environ.get(
    "TEST_GODOT_PROJECT_PATH", "/home/godotmentor/Projects/moebius_shader"
)
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"
SERVER_STARTUP_TIMEOUT = 10  # seconds

# @dataclass
# class CallToolResult:
#     content: list[mcp.types.ContentBlock]
#     structured_content: dict[str, Any] | None
#     meta: dict[str, Any] | None
#     data: Any = None
#     is_error: bool = False


@pytest.fixture(scope="session")
def mcp_server():
    """Start the MCP server before tests and stop it after."""

    # Kill any existing process on port 8000
    try:
        for proc in psutil.process_iter(["pid", "name", "connections"]):
            try:
                for conn in proc.net_connections():
                    if conn.laddr.port == 8000:
                        print(
                            f"\n⚠️  Killing existing process on port 8000 (PID: {proc.pid})"
                        )
                        proc.kill()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logger.error(f"Error checking/killing existing processes: {e}")

    # Small delay to ensure port is released
    time.sleep(1)

    # Start the server using uv
    process = subprocess.Popen(
        ["uv", "run", "main.py", "--http"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for server to be ready by checking if port 8000 is listening
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", 8000))
            sock.close()

            if result == 0:
                # Port is open, give it a moment to fully initialize
                time.sleep(0.5)
                server_ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not server_ready:
        process.kill()
        pytest.exit(
            "MCP server failed to start within timeout. Is port 8000 already in use?"
        )

    print(f"\n✓ MCP server started successfully (PID: {process.pid})")

    yield process

    # Cleanup: stop the server and all child processes
    print("\n✓ Stopping MCP server...")
    try:
        # Get all child processes
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)

        # Terminate parent
        process.terminate()

        # Wait a bit for graceful shutdown
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # Force kill if needed
            process.kill()

        # Kill any remaining children
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass

    except Exception as e:
        logger.error(f"⚠️  Error during cleanup: {e}")
        try:
            process.kill()
        except:  # noqa: E722
            pass

    print("✓ MCP server stopped")


@pytest.fixture
async def mcp_client(mcp_server):
    """Create an MCP client for testing."""
    client = Client(MCP_SERVER_URL)
    async with client:
        yield client


@pytest.fixture
def temp_godot_project():
    """Create a temporary Godot project structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Create a minimal project.godot file
        project_file = project_path / "project.godot"
        project_file.write_text("""[application]

config/name="Test Project"
config/features=PackedStringArray("4.3")

[rendering]

renderer/rendering_method="forward_plus"
""")

        # Create some test files
        (project_path / "main.tscn").write_text("[gd_scene load_steps=1 format=3]")
        (project_path / "player.gd").write_text("extends Node\n")
        (project_path / "assets").mkdir()
        (project_path / "assets" / "icon.png").write_bytes(b"fake_png_data")

        yield str(project_path)


@pytest.mark.integration
class TestListProjects:
    """Tests for list_projects tool."""

    @pytest.mark.asyncio
    async def test_list_projects_non_recursive(self, mcp_client, temp_godot_project):
        """Test listing projects in a directory without recursion."""
        parent_dir = str(Path(temp_godot_project).parent)

        result: CallToolResult = await mcp_client.call_tool(
            "list_projects", {"directory": parent_dir, "recursive": False}
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]

        # Parse the JSON response
        projects = json.loads(text_content)
        assert isinstance(projects, list)
        assert len(projects) >= 1

        # Check that our temp project is in the list
        project_names = [p["name"] for p in projects]
        assert "test_project" in project_names

    @pytest.mark.asyncio
    async def test_list_projects_recursive(self, mcp_client, temp_godot_project):
        """Test listing projects recursively."""
        parent_dir = str(Path(temp_godot_project).parent.parent)

        result: CallToolResult = await mcp_client.call_tool(
            "list_projects", {"directory": parent_dir, "recursive": True}
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        projects = json.loads(text_content)
        assert isinstance(projects, list)

    @pytest.mark.asyncio
    async def test_list_projects_invalid_path(self, mcp_client):
        """Test listing projects with invalid path."""
        result: CallToolResult = await mcp_client.call_tool(
            "list_projects", {"directory": "/nonexistent/path/that/does/not/exist"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "does not exist" in text_content.lower()

    @pytest.mark.asyncio
    async def test_list_projects_path_traversal(self, mcp_client):
        """Test that path traversal is blocked."""
        result: CallToolResult = await mcp_client.call_tool(
            "list_projects", {"directory": "/home/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "path traversal" in text_content.lower()

    @pytest.mark.asyncio
    async def test_list_projects_empty_directory(self, mcp_client):
        """Test listing projects in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result: CallToolResult = await mcp_client.call_tool(
                "list_projects", {"directory": tmpdir, "recursive": False}
            )

            assert result is not None
            assert result.is_error is False

            data = result.data
            text_content = data["content"][0]["text"]
            projects = json.loads(text_content)
            assert isinstance(projects, list)
            assert len(projects) == 0


@pytest.mark.integration
class TestGetProjectInfo:
    """Tests for get_project_info tool."""

    @pytest.mark.asyncio
    async def test_get_project_info_valid_project(self, mcp_client, temp_godot_project):
        """Test getting info from a valid Godot project."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_info", {"project_path": temp_godot_project}
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        dict_content = json.loads(text_content)

        # Check required fields
        assert "name" in text_content
        assert "path" in text_content
        assert "godotVersion" in text_content
        assert "structure" in text_content

        # Check project name is correctly extracted
        assert dict_content["name"] == "Test Project"
        assert "/tmp" in dict_content["path"]
        assert "test_project" in dict_content["path"]

        # Verify structure counts
        structure = dict_content["structure"]
        assert "scenes" in structure
        assert "scripts" in structure
        assert "assets" in structure
        assert "other" in structure

        # Check our temp project has the expected files
        assert structure["scenes"] >= 1  # main.tscn
        assert structure["scripts"] >= 1  # player.gd
        assert structure["assets"] >= 1  # icon.png

        # Godot version should be non-empty
        assert len(dict_content["godotVersion"]) > 0

    @pytest.mark.asyncio
    async def test_get_project_info_real_project(self, mcp_client):
        """Test getting info from the real test project."""
        if not Path(TEST_PROJECT_PATH).exists():
            pytest.skip(f"Test project not found at {TEST_PROJECT_PATH}")

        result: CallToolResult = await mcp_client.call_tool(
            "get_project_info", {"project_path": TEST_PROJECT_PATH}
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        info = json.loads(text_content)

        assert info["name"]  # Should have a name
        assert info["path"] == TEST_PROJECT_PATH
        assert "godotVersion" in info

        # Real project should have some structure
        structure = info["structure"]
        total_files = sum(structure.values())
        assert total_files > 0, "Real project should have some files"

    @pytest.mark.asyncio
    async def test_get_project_info_invalid_project(self, mcp_client):
        """Test getting info from an invalid project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Directory exists but no project.godot
            result: CallToolResult = await mcp_client.call_tool(
                "get_project_info", {"project_path": tmpdir}
            )

            data = result.data
            text_content = data["content"][0]["text"]

            assert data["is_error"] is True
            assert "not a valid godot project" in text_content.lower()

    @pytest.mark.asyncio
    async def test_get_project_info_path_traversal(self, mcp_client):
        """Test that path traversal is blocked."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_info", {"project_path": "/home/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "invalid project path" in text_content.lower()

    @pytest.mark.asyncio
    async def test_get_project_info_missing_path(self, mcp_client):
        """Test getting info with missing project path."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_info", {"project_path": ""}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "required" in text_content.lower()


@pytest.mark.integration
class TestGetProjectStructure:
    """Tests for get_project_structure tool."""

    @pytest.mark.asyncio
    async def test_get_project_structure_basic(self, mcp_client, temp_godot_project):
        """Test getting project structure."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_structure", {"project_path": temp_godot_project}
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]

        # Parse the tree structure
        tree = json.loads(text_content)

        assert tree["type"] == "directory"
        assert "children" in tree
        assert len(tree["children"]) > 0

        # Check that our test files are in the tree
        child_names = [child["name"] for child in tree["children"]]
        assert "main.tscn" in child_names
        assert "player.gd" in child_names
        assert "assets" in child_names

        # Check that assets directory has children
        assets_dir = next(c for c in tree["children"] if c["name"] == "assets")
        assert assets_dir["type"] == "directory"
        assert "children" in assets_dir
        assert len(assets_dir["children"]) > 0

    @pytest.mark.asyncio
    async def test_get_project_structure_max_depth(
        self, mcp_client, temp_godot_project
    ):
        """Test getting project structure with max depth limit."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_structure",
            {"project_path": temp_godot_project, "max_depth": 1},
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        tree = json.loads(text_content)

        # Should have children at first level
        assert len(tree["children"]) > 0

        # Check that directories don't have their children populated
        for child in tree["children"]:
            if child["type"] == "directory":
                # With max_depth=1, subdirectories should have no children
                assert len(child.get("children", [])) == 0

    @pytest.mark.asyncio
    async def test_get_project_structure_zero_depth(
        self, mcp_client, temp_godot_project
    ):
        """Test getting project structure with zero depth."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_structure",
            {"project_path": temp_godot_project, "max_depth": 0},
        )

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        tree = json.loads(text_content)

        # Should return only the root with no children
        assert tree["type"] == "directory"
        assert len(tree.get("children", [])) == 0

    @pytest.mark.asyncio
    async def test_get_project_structure_invalid_path(self, mcp_client):
        """Test getting structure with invalid path."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_structure", {"project_path": "/nonexistent/path/xyz123"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "does not exist" in text_content.lower()

    @pytest.mark.asyncio
    async def test_get_project_structure_path_traversal(self, mcp_client):
        """Test that path traversal is blocked."""
        result: CallToolResult = await mcp_client.call_tool(
            "get_project_structure", {"project_path": "/tmp/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "path traversal" in text_content.lower()


@pytest.mark.integration
class TestLaunchEditor:
    """Tests for launch_editor tool."""

    @pytest.mark.asyncio
    async def test_launch_editor_invalid_project(self, mcp_client):
        """Test launching editor with invalid project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result: CallToolResult = await mcp_client.call_tool(
                "launch_editor", {"project_path": tmpdir}
            )

            data = result.data
            text_content = data["content"][0]["text"]

            assert data["is_error"] is True
            assert "not a valid godot project" in text_content.lower()

    @pytest.mark.asyncio
    async def test_launch_editor_path_traversal(self, mcp_client):
        """Test that path traversal is blocked."""
        result: CallToolResult = await mcp_client.call_tool(
            "launch_editor", {"project_path": "/home/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "path traversal" in text_content.lower()

    @pytest.mark.asyncio
    async def test_launch_editor_missing_path(self, mcp_client):
        """Test launching editor with missing path."""
        result: CallToolResult = await mcp_client.call_tool(
            "launch_editor", {"project_path": ""}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "required" in text_content.lower()

    # Note: We don't test actual editor launch as it would spawn a GUI process
    # and is not suitable for automated testing


@pytest.mark.integration
class TestGetGodotVersionAlias:
    """Tests for get_godot_version tool alias."""

    @pytest.mark.asyncio
    async def test_get_godot_version(self, mcp_client):
        result: CallToolResult = await mcp_client.call_tool("get_godot_version", {})

        assert result is not None
        assert result.is_error is False

        data = result.data
        text_content = data["content"][0]["text"]
        assert len(text_content) > 0


@pytest.mark.integration
class TestUpdateProjectUidsAlias:
    """Tests for update_project_uids tool alias."""

    @pytest.mark.asyncio
    async def test_update_project_uids_path_traversal(self, mcp_client):
        result: CallToolResult = await mcp_client.call_tool(
            "update_project_uids", {"project_path": "/tmp/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "path traversal" in text_content.lower()


@pytest.mark.integration
class TestRunProject:
    """Tests for run_project tool."""

    @pytest.mark.asyncio
    async def test_run_project_invalid_project(self, mcp_client):
        with tempfile.TemporaryDirectory() as tmpdir:
            result: CallToolResult = await mcp_client.call_tool(
                "run_project", {"project_path": tmpdir}
            )

            data = result.data
            text_content = data["content"][0]["text"]

            assert data["is_error"] is True
            assert "not a valid godot project" in text_content.lower()

    @pytest.mark.asyncio
    async def test_run_project_path_traversal(self, mcp_client):
        result: CallToolResult = await mcp_client.call_tool(
            "run_project", {"project_path": "/tmp/../etc"}
        )

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "path traversal" in text_content.lower()


@pytest.mark.integration
class TestGetDebugOutput:
    """Tests for get_debug_output tool."""

    @pytest.mark.asyncio
    async def test_get_debug_output_no_process(self, mcp_client):
        result: CallToolResult = await mcp_client.call_tool("get_debug_output", {})

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "no active godot process" in text_content.lower()


@pytest.mark.integration
class TestStopProject:
    """Tests for stop_project tool."""

    @pytest.mark.asyncio
    async def test_stop_project_no_process(self, mcp_client):
        result: CallToolResult = await mcp_client.call_tool("stop_project", {})

        data = result.data
        text_content = data["content"][0]["text"]

        assert data["is_error"] is True
        assert "no active godot process" in text_content.lower()
