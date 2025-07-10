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

    # Use the standalone MCP launcher that sets environment before any imports
    mcp_launcher_path = (
        Path(__file__).parent.parent.parent.parent.parent / "mcp_launcher.py"
    )
    cmd = [sys.executable, str(mcp_launcher_path)]

    # Handle positional path argument for complete project scope control
    if hasattr(args, 'path') and args.path != Path("."):
        project_path = args.path.resolve()

        # Set database path to <path>/.chunkhound/db if not explicitly provided
        if args.db is None:
            db_path = project_path / ".chunkhound" / "db"
            cmd.extend(["--db", str(db_path)])
        else:
            cmd.extend(["--db", str(args.db)])

        # Set watch path to the project directory
        cmd.extend(["--watch-path", str(project_path)])

    else:
        # Only pass --db if explicitly provided, let unified config handle defaults
        if args.db is not None:
            cmd.extend(["--db", str(args.db)])

    # Inherit current environment - the centralized config will handle API keys
    env = os.environ.copy()

    # Preserve virtual environment context for Ubuntu/Linux compatibility
    # This fixes the TaskGroup -32603 error when subprocess loses venv context

    # 1. Preserve Python module search paths
    env["PYTHONPATH"] = ":".join(sys.path)

    # 2. Pass virtual environment information
    if hasattr(sys, "prefix"):
        env["VIRTUAL_ENV"] = sys.prefix

    # 3. Ensure PATH includes venv bin directory
    # Check if we're in a virtualenv
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if in_venv:
        # Add venv bin to PATH to find correct Python and tools
        venv_bin = Path(sys.prefix) / "bin"
        current_path = env.get("PATH", "")
        env["PATH"] = f"{venv_bin}:{current_path}"

        # Also try to use venv Python directly if available
        venv_python = venv_bin / "python"
        if venv_python.exists():
            cmd[0] = str(venv_python)

    # Set environment variable for config file search if path provided
    if hasattr(args, 'path') and args.path != Path("."):
        env["CHUNKHOUND_PROJECT_ROOT"] = str(args.path.resolve())

    process = subprocess.run(
        cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,  # Allow stderr for MCP SDK internal error handling
        env=env,  # Pass environment variables to subprocess
    )

    # Exit with the same code as the subprocess
    sys.exit(process.returncode)


__all__: list[str] = ["mcp_command"]
