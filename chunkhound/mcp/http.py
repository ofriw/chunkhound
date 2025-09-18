"""HTTP MCP server implementation using the base class pattern.

This module implements the HTTP transport for MCP using FastMCP,
inheriting common initialization and lifecycle management from MCPServerBase.

Unlike stdio, HTTP servers can use lazy initialization and don't require
global state management.
"""

from typing import Any

from fastmcp import FastMCP

from chunkhound.core.config.config import Config

from .base import MCPServerBase
from .common import handle_tool_call
from .tools import TOOL_REGISTRY, Tool


class HttpMCPServer(MCPServerBase):
    """MCP server implementation for HTTP protocol using FastMCP.

    Uses lazy initialization pattern - services are initialized on first
    request rather than at startup. This is more suitable for HTTP's
    request/response model.
    """

    def __init__(self, config: Config, port: int = 5173):
        """Initialize HTTP MCP server.

        Args:
            config: Validated configuration object
            port: Port to listen on (default: 5173)
        """
        super().__init__(config)
        self.port = port

        # Create FastMCP instance
        self.app: FastMCP = FastMCP("ChunkHound Code Search")

        # Register tools with the server
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all tools from the registry with FastMCP."""
        import asyncio
        import json

        import mcp.types as types

        # Auto-register all tools from registry
        for tool_name, tool_def in TOOL_REGISTRY.items():
            # Skip embedding tools if no provider configured
            if tool_def.requires_embeddings and not self.embedding_manager:
                continue

            # Create a closure to capture tool_name correctly
            def create_handler(name: str, tool: Tool) -> Any:
                async def tool_handler(**kwargs: Any) -> dict[str, Any]:
                    """Auto-generated handler from registry."""
                    # Create an initialization event for this request
                    init_event = asyncio.Event()

                    # Ensure initialization
                    await self.initialize()
                    init_event.set()

                    # FastMCP passes params as kwargs, convert to dict
                    result = await handle_tool_call(
                        tool_name=name,
                        arguments=kwargs,
                        services=self.ensure_services(),
                        embedding_manager=self.embedding_manager,
                        initialization_complete=init_event,
                        debug_mode=self.debug_mode,
                        scan_progress=self._scan_progress,
                    )

                    # Convert TextContent list to dict for FastMCP
                    if result and isinstance(result[0], types.TextContent):
                        parsed_result: dict[str, Any] = json.loads(result[0].text)
                        return parsed_result
                    return {"error": "Invalid response format"}

                # Set the handler's name and docstring from tool definition
                tool_handler.__name__ = name
                tool_handler.__doc__ = tool.description
                return tool_handler

            # Register with FastMCP using tool metadata from registry
            handler = create_handler(tool_name, tool_def)
            self.app.tool()(handler)

    async def run(self) -> None:
        """Run the HTTP server.

        FastMCP handles most of the lifecycle management, so this is simpler
        than the stdio implementation.
        """
        try:
            self.debug_log(f"Starting HTTP server on port {self.port}")

            # Run the FastMCP server in HTTP mode
            await self.app.run_http_async(port=self.port, host="0.0.0.0")

        except KeyboardInterrupt:
            self.debug_log("Server interrupted by user")
        except Exception as e:
            self.debug_log(f"Server error: {e}")
            if self.debug_mode:
                import traceback

                traceback.print_exc()
        finally:
            # Cleanup resources
            await self.cleanup()
            self.debug_log("Server shutdown complete")


async def main() -> None:
    """Main entry point for HTTP server"""
    import argparse
    import sys

    from chunkhound.api.cli.utils.config_factory import create_validated_config
    from chunkhound.mcp.common import add_common_mcp_arguments

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
    import asyncio

    asyncio.run(main())
