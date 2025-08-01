"""MCP command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path
from typing import Any, cast

from chunkhound.core.config.database_config import DatabaseConfig
from chunkhound.core.config.mcp_config import MCPConfig


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
    mcp_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    mcp_parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file path",
    )
    mcp_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    # Add config-specific arguments
    DatabaseConfig.add_cli_arguments(mcp_parser)
    MCPConfig.add_cli_arguments(mcp_parser)

    return cast(argparse.ArgumentParser, mcp_parser)


__all__: list[str] = ["add_mcp_subparser"]
