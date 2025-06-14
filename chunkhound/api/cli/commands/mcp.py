"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import os
from pathlib import Path


def mcp_command(args: argparse.Namespace) -> None:
    """Execute the MCP server command.

    Args:
        args: Parsed command-line arguments containing database path
    """
    import subprocess
    import sys

    # Determine if we're running from a PyInstaller bundle
    def is_pyinstaller_bundle():
        return hasattr(sys, '_MEIPASS') or hasattr(sys, 'frozen')

    # Get the correct path to mcp_launcher.py
    if is_pyinstaller_bundle():
        # Running from PyInstaller bundle - use the bundled launcher
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller one-folder mode
            mcp_launcher_path = Path(sys._MEIPASS) / "mcp_launcher.py"
        else:
            # PyInstaller one-file mode or other frozen
            mcp_launcher_path = Path(sys.executable).parent / "_internal" / "mcp_launcher.py"
    else:
        # Running from source - use relative path
        mcp_launcher_path = Path(__file__).parent.parent.parent.parent.parent / "mcp_launcher.py"

    # Fallback: if the path doesn't exist, try to find it
    if not mcp_launcher_path.exists():
        # Try alternative locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent.parent / "mcp_launcher.py",
            Path(sys.executable).parent / "mcp_launcher.py",
            Path.cwd() / "mcp_launcher.py",
        ]

        for path in possible_paths:
            if path.exists():
                mcp_launcher_path = path
                break
        else:
            # If we still can't find it, run the MCP server directly
            os.environ["CHUNKHOUND_DB_PATH"] = str(args.db)
            try:
                from chunkhound.mcp_entry import main_sync
                main_sync()
                return
            except Exception as e:
                print(f"Error starting MCP server: {e}", file=sys.stderr)
                sys.exit(1)

    cmd = [sys.executable, str(mcp_launcher_path), "--db", str(args.db)]

    process = subprocess.run(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr  # Allow stderr through for proper error handling
    )

    # Exit with the same code as the subprocess
    sys.exit(process.returncode)


def add_mcp_subparser(subparsers) -> argparse.ArgumentParser:
    """Add MCP command subparser to the main parser.

    Args:
        subparsers: Subparsers object from the main argument parser

    Returns:
        The configured MCP subparser
    """
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run Model Context Protocol server",
        description="Start the MCP server for integration with MCP-compatible clients"
    )

    mcp_parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".cache" / "chunkhound" / "chunks.duckdb",
        help="DuckDB database file path (default: ~/.cache/chunkhound/chunks.duckdb)",
    )

    return mcp_parser


__all__ = ["mcp_command", "add_mcp_subparser"]
