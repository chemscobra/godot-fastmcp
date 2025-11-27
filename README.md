# godot-fastmcp

Modular Python implementation of https://github.com/Coding-Solo/godot-mcp adapter using FastMCP. Inspired by and giving full credit to Coding-Solo's godot-mcp — this repo reimplements and modularizes that work in Python (no Node.js).

## Purpose

Provide a small set of tools to interact with Godot projects (launch editor, run projects, list projects, inspect/debug output, project/scene helpers) via FastMCP so you can embed Godot operations into tooling or a language model workflow.

## Key files

- main.py — Python entrypoint that registers tools and starts the FastMCP server.
- tools/ — Modular tool implementations (one module per tool or grouped logically).
- models/ — Pydantic models for ToolResponse / ContentItem and shared types.
- gd_scripts/godot_operations.gd — Godot script used by some tools (headless mode).
- server.py — example client for calling tools over the MCP.
- README.md — this file.

## Requirements

- Python 3.12+
- fastmcp
- Godot Engine installed and accessible (set GODOT_PATH if needed)

Install basics:
```sh
uv sync
```

## Quick start

1. Configure environment (optional):
```sh
export GODOT_PATH=/usr/bin/godot
export GODOT_OPERATIONS_SCRIPT=path/to/godot_operations.gd
```

2. Run the MCP server :
```sh
# stdio transport
uv run main.py
# http transport
uv run main.py --http


## Tools (examples)

- get_godot_version — return Godot version
- launch_editor — open Godot editor for a project
- run_project / stop_project — start/stop Godot in debug/headless mode
- list_projects — find Godot projects in a directory
- get_debug_output — fetch runtime output for the active process

Each tool returns a structured ToolResponse (see models/).

## Project layout recommendation

Tool modules are split under tools/ for maintainability (one file per tool or grouped by responsibility). Register tools in main.py via a tools.__init__ that imports and registers each tool with FastMCP.

## Contributing

- Give credit to the original project: https://github.com/Coding-Solo/godot-mcp
- Add tests under tests/
- Keep tools small and focused; prefer one-file-per-tool for easier testing and maintenance.

## License & credits

This project reimplements ideas from Coding-Solo/godot-mcp in Python with FastMCP. Give credit to the original author when using concepts or ported code.

