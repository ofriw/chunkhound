#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol

This module now serves as a thin wrapper around the new MCP architecture,
maintaining backward compatibility while delegating to the StdioMCPServer class.
"""

import argparse
import asyncio
import logging
import sys

# CRITICAL: Disable ALL logging to prevent JSON-RPC corruption
logging.disable(logging.CRITICAL)

# Import the new architecture
from chunkhound.api.cli.utils.config_factory import create_validated_config
from chunkhound.mcp.stdio import StdioMCPServer
from chunkhound.mcp_shared import add_common_mcp_arguments


async def main(args: argparse.Namespace | None = None) -> None:
    """Main entry point for the MCP server with robust error handling.

    Args:
        args: Pre-parsed arguments. If None, will parse from sys.argv.
    """
    # Import debug_log early to use it
    from chunkhound.mcp_common import debug_log
    debug_log("MCP server main() started")
    
    if args is None:
        # Direct invocation - parse arguments
        parser = argparse.ArgumentParser(
            description="ChunkHound MCP stdio server",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        # Add common MCP arguments
        add_common_mcp_arguments(parser)
        # Parse arguments
        args = parser.parse_args()

    # Create and validate configuration
    config, validation_errors = create_validated_config(args, "mcp")

    if validation_errors:
        # CRITICAL: Cannot print to stderr in MCP mode - breaks JSON-RPC protocol
        # Exit silently with error code
        sys.exit(1)

    # Create and run the stdio server
    server = StdioMCPServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
