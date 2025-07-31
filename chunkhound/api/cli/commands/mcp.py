"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import os
import sys
from pathlib import Path


async def mcp_command(args: argparse.Namespace) -> None:
    """Execute the MCP server command.

    Args:
        args: Parsed command-line arguments containing database path
    """
    # Set MCP mode environment early
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    # CRITICAL: Import numpy modules early for DuckDB threading safety in MCP mode
    # Must happen before any DuckDB operations in async/threading context
    # See: https://duckdb.org/docs/stable/clients/python/known_issues.html
    try:
        import numpy  # noqa: F401
    except ImportError:
        pass

    # Set database path environment variable if provided
    if hasattr(args, "db") and args.db:
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(args.db)
    elif hasattr(args, "path") and args.path != Path("."):
        # Set default database path based on project path
        project_path = args.path.resolve()
        db_path = project_path / ".chunkhound" / "db"
        os.environ["CHUNKHOUND_DATABASE__PATH"] = str(db_path)

    # Handle transport selection
    if hasattr(args, "http") and args.http:
        # Use HTTP transport via subprocess to avoid event loop conflicts
        import subprocess

        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)

        # Run HTTP server in subprocess
        cmd = [
            sys.executable,
            "-m",
            "chunkhound.mcp_http_server",
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
        from chunkhound.mcp_server import main

        await main(args=args)


__all__: list[str] = ["mcp_command"]
