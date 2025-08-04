#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP

This module now serves as a thin wrapper around the new MCP architecture,
maintaining backward compatibility while delegating to the HttpMCPServer class.
"""

import argparse
import asyncio
import sys

# Import the new architecture
from chunkhound.api.cli.utils.config_factory import create_validated_config
from chunkhound.mcp.http import HttpMCPServer
from chunkhound.mcp_shared import add_common_mcp_arguments


async def main() -> None:
    """Main entry point for HTTP server"""
    parser = argparse.ArgumentParser(
        description="ChunkHound MCP HTTP server (FastMCP 2.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add common MCP arguments
    add_common_mcp_arguments(parser)

    # HTTP-specific arguments
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5173, help="Port to bind to")

    args = parser.parse_args()

    # Create and validate configuration
    config, validation_errors = create_validated_config(args, "mcp")

    if validation_errors:
        for error in validation_errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    # Create and run the HTTP server
    server = HttpMCPServer(config, port=args.port)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
