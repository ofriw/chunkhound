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
    
    print(f"mcp_command called with args: {args}", file=sys.stderr)

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

    # Handle transport selection
    if hasattr(args, 'http') and args.http:
        cmd.extend(["--transport", "http"])
        
        # Add host and port for HTTP transport
        if hasattr(args, 'host'):
            cmd.extend(["--host", args.host])
        if hasattr(args, 'port'):
            cmd.extend(["--port", str(args.port)])
    else:
        # Default to stdio transport
        cmd.extend(["--transport", "stdio"])

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

    # For HTTP transport, call directly to avoid subprocess issues
    if hasattr(args, 'http') and args.http:
        # Set environment variables
        for key, value in env.items():
            os.environ[key] = value
        
        print(f"About to import HTTP server...", file=sys.stderr)
        
        # Import and run HTTP server directly
        from chunkhound.mcp_http_server import main as http_main
        
        print(f"HTTP server imported, setting up argv...", file=sys.stderr)
        
        # Override sys.argv for the HTTP server
        sys.argv = [
            "mcp_http_server",
            "--host", getattr(args, 'host', '127.0.0.1'),
            "--port", str(getattr(args, 'port', 8000)),
        ]
        
        print(f"About to call http_main()...", file=sys.stderr)
        
        # Call HTTP server main function
        http_main()
    else:
        # For stdio transport, use subprocess.run as before
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
