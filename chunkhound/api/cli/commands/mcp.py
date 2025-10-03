"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import json
import os
import sys
from pathlib import Path

from chunkhound.utils.windows_constants import IS_WINDOWS


def _safe_print(text: str) -> None:
    """Print text with safe encoding for all platforms."""
    try:
        # On Windows, ensure UTF-8 encoding for console output
        if IS_WINDOWS:
            # Try to encode as UTF-8 first
            try:
                print(text.encode("utf-8").decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                # Fallback to ASCII-safe version
                safe_text = text.encode("ascii", errors="replace").decode("ascii")
                print(safe_text)
        else:
            # Unix systems typically handle UTF-8 better
            print(text)
    except Exception:
        # Final fallback - strip any non-ASCII characters
        safe_text = "".join(c if ord(c) < 128 else "?" for c in text)
        print(safe_text)


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

        # Set up environment with UTF-8 encoding for Windows compatibility
        from chunkhound.utils.windows_constants import get_utf8_env

        env = get_utf8_env()

        process = subprocess.run(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
            encoding="utf-8",
            errors="replace",  # Handle encoding errors gracefully
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

    # Show setup instructions with cross-platform safe output
    _safe_print("\n[MCP] Server Configuration")
    _safe_print("=" * 30)  # Use ASCII characters instead of Unicode
    _safe_print("\nTo use ChunkHound in Claude Desktop or VS Code:")
    _safe_print("\nAdd to ~/.claude/claude_desktop_config.json:")

    config_snippet = {
        "mcpServers": {
            "chunkhound": {
                "command": "uv",
                "args": ["run", "chunkhound", "mcp", str(project_path.absolute())],
            }
        }
    }

    _safe_print(json.dumps(config_snippet, indent=2))

    try:
        import pyperclip

        pyperclip.copy(json.dumps(config_snippet, indent=2))
        # Use ASCII clipboard icon instead of Unicode
        _safe_print("\n[COPIED] Configuration copied to clipboard!")
    except (ImportError, Exception):
        pass  # pyperclip is optional and may fail in headless environments

    _safe_print(f"\nStarting MCP server for {project_path.name}...")
    _safe_print("Ready for connections from Claude Desktop or other MCP clients.\n")

    # Create marker file
    try:
        with open(marker_path, "w") as f:
            f.write("MCP setup instructions shown")
    except Exception:
        pass  # Not critical if we can't create marker


__all__: list[str] = ["mcp_command"]
