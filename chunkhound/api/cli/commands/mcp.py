"""MCP command module - handles Model Context Protocol server operations."""

import argparse
import asyncio
import os
from pathlib import Path
from loguru import logger


def mcp_command(args: argparse.Namespace) -> None:
    """Execute the MCP server command.
    
    Args:
        args: Parsed command-line arguments containing database path
    """
    # Set database path in environment for MCP server
    os.environ["CHUNKHOUND_DB_PATH"] = str(args.db)
    
    # No logging output for MCP server - must maintain clean stdin/stdout for JSON-RPC
    logger.remove()
    
    # Import and run MCP server
    from chunkhound.mcp_server import main as run_mcp_server
    asyncio.run(run_mcp_server())


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