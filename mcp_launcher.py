#!/usr/bin/env python3
"""
ChunkHound MCP Launcher - Entry point script for Model Context Protocol server

This launcher script sets the MCP mode environment variable and redirects to
the main MCP entry point in chunkhound.mcp_entry. It's designed to be called
from the CLI commands that need to start an MCP server with clean JSON-RPC
communication (no logging or other output that would interfere with the protocol).
"""

import os
import sys
import argparse
from pathlib import Path


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ChunkHound MCP Server")
    parser.add_argument(
        "--db",
        type=str,
        help="Path to DuckDB database file",
        default=str(Path.home() / ".cache" / "chunkhound" / "chunks.duckdb")
    )
    return parser.parse_args()


def main():
    """Set up environment and launch MCP server."""
    # Parse arguments
    args = parse_arguments()
    
    # Set required environment variables
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    os.environ["CHUNKHOUND_DB_PATH"] = args.db
    
    # Import and run the MCP entry point
    try:
        from chunkhound.mcp_entry import main_sync
        main_sync()
    except ImportError:
        print("Error: Could not import chunkhound.mcp_entry", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()