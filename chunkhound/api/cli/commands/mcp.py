"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import json
import os
import sys
from pathlib import Path


async def mcp_command(args: argparse.Namespace, config) -> None:
    """Execute the MCP server command.

    Args:
        args: Parsed command-line arguments containing database path
        config: Pre-validated configuration instance
    """
    # Show MCP setup instructions on first run
    _show_mcp_setup_instructions_if_first_run(args)

    # Set MCP mode environment early
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    # CRITICAL: Import numpy modules early for DuckDB threading safety in MCP mode
    # Must happen before any DuckDB operations in async/threading context
    # See: https://duckdb.org/docs/stable/clients/python/known_issues.html
    try:
        import numpy  # noqa: F401
    except ImportError:
        pass


    # Handle transport selection
    if hasattr(args, "http") and args.http:
        # Use HTTP transport via subprocess to avoid event loop conflicts
        import subprocess

        # Use config values instead of hardcoded fallbacks
        # CLI args override config values
        host = getattr(args, "host", None) or config.mcp.host
        port = getattr(args, "port", None) or config.mcp.port

        # Run HTTP server in subprocess
        cmd = [
            sys.executable,
            "-m",
            "chunkhound.mcp.http_server",
            "--host",
            str(host),
            "--port",
            str(port),
        ]

        if hasattr(args, "db") and args.db:
            cmd.extend(["--db", str(args.db)])

        process = subprocess.run(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=os.environ.copy(),
        )
        sys.exit(process.returncode)
    else:
        # Use stdio transport (default)
        from chunkhound.mcp.stdio import main

        await main(args=args)


def _show_mcp_setup_instructions_if_first_run(args: argparse.Namespace) -> None:
    """Show MCP setup instructions on first run."""
    # Check if this looks like a first run (recent .chunkhound.json)
    project_path = Path(args.path)
    config_path = project_path / ".chunkhound.json"

    # Skip if no config file exists
    if not config_path.exists():
        return

    # Check if .chunkhound.json is very recent (created in last 5 minutes)
    import time
    file_age_seconds = time.time() - config_path.stat().st_mtime
    if file_age_seconds > 300:  # More than 5 minutes old
        return

    # Only show once by creating a marker file
    marker_path = project_path / ".chunkhound" / ".mcp_setup_shown"
    if marker_path.exists():
        return

    # Create marker directory if needed
    marker_path.parent.mkdir(exist_ok=True)

    # Show setup instructions
    print("\n🔌 MCP Server Configuration")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("\nTo use ChunkHound in Claude Desktop or VS Code:")
    print("\nAdd to ~/.claude/claude_desktop_config.json:")

    config_snippet = {
        "mcpServers": {
            "chunkhound": {
                "command": "uv",
                "args": ["run", "chunkhound", "mcp", str(project_path.absolute())]
            }
        }
    }

    print(json.dumps(config_snippet, indent=2))

    try:
        import pyperclip
        pyperclip.copy(json.dumps(config_snippet, indent=2))
        print("\n📋 Configuration copied to clipboard!")
    except (ImportError, Exception):
        pass  # pyperclip is optional and may fail in headless environments

    print(f"\nStarting MCP server for {project_path.name}...")
    print("Ready for connections from Claude Desktop or other MCP clients.\n")

    # Create marker file
    try:
        with open(marker_path, 'w') as f:
            f.write("MCP setup instructions shown")
    except Exception:
        pass  # Not critical if we can't create marker


__all__: list[str] = ["mcp_command"]
