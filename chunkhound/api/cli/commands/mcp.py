"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import os
from pathlib import Path
from typing import Any, cast


def mcp_command(args: argparse.Namespace) -> None:
    """Execute the MCP server command.

    Args:
        args: Parsed command-line arguments containing database path
    """
    import subprocess
    import sys

    # Use the standalone MCP launcher that sets environment before any imports
    mcp_launcher_path = (
        Path(__file__).parent.parent.parent.parent.parent / "mcp_launcher.py"
    )
    cmd = [sys.executable, str(mcp_launcher_path)]

    # Only pass --db argument if explicitly provided, otherwise let unified config handle it
    if args.db is not None:
        cmd.extend(["--db", str(args.db)])

    # Pass the path argument as watch-path if provided and not current directory
    if hasattr(args, 'path') and args.path != Path("."):
        cmd.extend(["--watch-path", str(args.path.resolve())])

    # Inherit current environment - the centralized config will handle API keys
    env = os.environ.copy()

    process = subprocess.run(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,  # Allow stderr for MCP SDK internal error handling
        env=env,  # Pass environment variables to subprocess
    )

    # Exit with the same code as the subprocess
    sys.exit(process.returncode)


def add_mcp_subparser(subparsers: Any) -> argparse.ArgumentParser:
    """Add MCP command subparser to the main parser.

    Args:
        subparsers: Subparsers object from the main argument parser

    Returns:
        The configured MCP subparser
    """
    from chunkhound.api.cli.parsers.main_parser import add_database_argument

    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run Model Context Protocol server",
        description="Start the MCP server for integration with MCP-compatible clients",
    )

    # Use shared database argument function to respect unified config
    add_database_argument(mcp_parser)

    return cast(argparse.ArgumentParser, mcp_parser)


__all__: list[str] = ["mcp_command", "add_mcp_subparser"]
