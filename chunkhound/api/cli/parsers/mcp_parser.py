"""MCP command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path

from .main_parser import add_common_arguments, add_database_argument


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
    
    # Add common arguments
    add_common_arguments(mcp_parser)
    add_database_argument(mcp_parser)
    
    # MCP-specific arguments
    mcp_parser.add_argument(
        "--stdio",
        action="store_true",
        default=True,
        help="Use stdio transport (default)",
    )
    
    mcp_parser.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP transport instead of stdio",
    )
    
    mcp_parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for HTTP transport (default: 3000)",
    )
    
    mcp_parser.add_argument(
        "--host",
        default="localhost",
        help="Host for HTTP transport (default: localhost)",
    )
    
    mcp_parser.add_argument(
        "--cors",
        action="store_true",
        help="Enable CORS for HTTP transport",
    )
    
    return mcp_parser


__all__ = ["add_mcp_subparser"]