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


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ChunkHound MCP Server")
    parser.add_argument(
        "--db", type=str, help="Path to DuckDB database file", default="chunkhound.db"
    )
    parser.add_argument(
        "--watch-path",
        type=str,
        help="Directory to watch for file changes (overrides auto-detection)",
        default=None,
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


def setup_watch_paths(args) -> None:
    """Set up watch paths for filesystem monitoring.

    Args:
        args: Parsed command line arguments
    """
    if args.watch_path:
        # Use explicitly provided watch path
        watch_path = Path(args.watch_path).resolve()
        if watch_path.exists() and watch_path.is_dir():
            os.environ["CHUNKHOUND_WATCH_PATHS"] = str(watch_path)
        else:
            # Log warning but don't fail - fall back to auto-detection
            # print(
            #     f"Warning: Specified watch path does not exist: {watch_path}",
            #     file=sys.stderr,
            # )
            os.environ["CHUNKHOUND_WATCH_PATHS"] = str(find_project_root())
    else:
        # Auto-detect project root
        project_root = find_project_root()
        os.environ["CHUNKHOUND_WATCH_PATHS"] = str(project_root)


def main():
    """Set up environment and launch MCP server."""
    # Parse arguments
    args = parse_arguments()

    # Set required environment variables
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    
    # Only set DB path if explicitly provided
    if args.db and args.db != "chunkhound.db":
        os.environ["CHUNKHOUND_DB_PATH"] = args.db

    # Set up watch paths for filesystem monitoring
    setup_watch_paths(args)

    # Import and run the MCP entry point
    try:
        from chunkhound.mcp_entry import main_sync

        main_sync()
    except ImportError:
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
