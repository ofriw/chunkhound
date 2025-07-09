"""MCP command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path
from typing import Any, cast

from .main_parser import (
    add_common_arguments,
    add_database_argument,
    add_indexing_arguments,
    add_mcp_arguments,
)


def add_mcp_subparser(subparsers: Any) -> argparse.ArgumentParser:
    """Add MCP command subparser to the main parser.

    Args:
        subparsers: Subparsers object from the main argument parser

    Returns:
        The configured MCP subparser
    """
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run Model Context Protocol server",
        description="Start the MCP server for integration with MCP-compatible clients",
    )

    # Optional positional argument with default to current directory
    mcp_parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Directory path to index (default: current directory)",
    )

    # Add common arguments
    add_common_arguments(mcp_parser)
    add_database_argument(mcp_parser)
    add_mcp_arguments(mcp_parser)
    add_indexing_arguments(mcp_parser)

    # MCP-specific legacy arguments for backwards compatibility
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

    return cast(argparse.ArgumentParser, mcp_parser)


__all__: list[str] = ["add_mcp_subparser"]
