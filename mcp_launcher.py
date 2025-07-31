#!/usr/bin/env python3
"""
ChunkHound MCP Launcher - Entry point script for Model Context Protocol server

This launcher script sets the MCP mode environment variable and redirects to
the main MCP entry point in chunkhound.mcp_entry. It's designed to be called
from the CLI commands that need to start an MCP server with clean JSON-RPC
communication (no logging or other output that would interfere with the protocol).
"""

import argparse
import os
import sys
from pathlib import Path

# Add the chunkhound package to Python path for imports
# This fixes the import error when running from different directories
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ChunkHound MCP Server")
    parser.add_argument(
        "--db", type=str, help="Path to DuckDB database file", default="chunkhound.db"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method (stdio or http)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (HTTP transport only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (HTTP transport only)"
    )
    return parser.parse_args()


def find_project_root(start_path: Path = None) -> Path:
    """Find the project root directory by looking for project indicators.

    Args:
        start_path: Directory to start searching from (defaults to current directory)

    Returns:
        Path to project root, or current directory if no project found
    """
    if start_path is None:
        start_path = Path.cwd()

    # Project indicators that suggest a project root
    project_indicators = [
        ".git",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        ".chunkhound",
    ]

    current = start_path.resolve()

    # Walk up the directory tree looking for project indicators
    while current != current.parent:  # Stop at filesystem root
        if any((current / indicator).exists() for indicator in project_indicators):
            return current
        current = current.parent

    # If no project root found, return the start path
    return start_path.resolve()




def main():
    """Set up environment and launch MCP server."""
    # Parse arguments
    args = parse_arguments()

    # Set required environment variables
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    
    # Set database path environment variable
    # This ensures the config system uses the correct database path
    if args.db:
        # Always set the environment variable when a path is provided
        # This includes paths like "/test-project/.chunkhound/db"
        os.environ["CHUNKHOUND_DATABASE__PATH"] = args.db



    # Import and run the appropriate MCP server based on transport
    try:
        if args.transport == "http":
            # Use HTTP transport with FastMCP via subprocess to avoid module state issues
            import subprocess
            
            http_cmd = [
                "uv", "run", "python", "-m", "chunkhound.mcp_http_server",
                "--host", args.host,
                "--port", str(args.port),
            ]
            if os.environ.get("CHUNKHOUND_DEBUG"):
                http_cmd.append("--debug")
            
            # Run HTTP server in subprocess to avoid module import conflicts
            process = subprocess.run(
                http_cmd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=os.environ.copy()
            )
            sys.exit(process.returncode)
        else:
            # Use stdio transport (default)
            from chunkhound.mcp_entry import main_sync
            main_sync()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
