"""Stdio MCP server implementation using the base class pattern.

This module implements the stdio (stdin/stdout) JSON-RPC protocol for MCP,
inheriting common initialization and lifecycle management from MCPServerBase.

CRITICAL: NO stdout output allowed - breaks JSON-RPC protocol
ARCHITECTURE: Global state required for stdio communication model
"""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from chunkhound.core.config.config import Config
from chunkhound.version import __version__

from .base import MCPServerBase
from .common import format_error_response, format_tool_response, parse_mcp_arguments
from .tools import TOOL_REGISTRY, execute_tool

# CRITICAL: Disable ALL logging to prevent JSON-RPC corruption
logging.disable(logging.CRITICAL)
for logger_name in ["", "mcp", "server", "fastmcp"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

# Disable loguru logger
try:
    from loguru import logger as loguru_logger

    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
except ImportError:
    pass


class StdioMCPServer(MCPServerBase):
    """MCP server implementation for stdio protocol.

    Uses global state as required by the stdio protocol's persistent
    connection model. All initialization happens eagerly during startup.
    """

    def __init__(self, config: Config, args: Any = None):
        """Initialize stdio MCP server.

        Args:
            config: Validated configuration object
            args: Original CLI arguments for direct path access
        """
        super().__init__(config, args=args)

        # Create MCP server instance
        self.server: Server = Server("ChunkHound Code Search")

        # Event to signal initialization completion
        self._initialization_complete = asyncio.Event()

        # Register tools with the server
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all tools from the registry with the stdio server."""

        # Register individual tool handlers with specific signatures
        # like the HTTP server does - this is what MCP expects
        
        @self.server.call_tool("get_stats")
        async def get_stats() -> list[types.TextContent]:
            """Get database statistics including file, chunk, and embedding counts"""
            # Direct implementation - no routing through _handle_tool_call
            try:
                await asyncio.wait_for(
                    self._initialization_complete.wait(), timeout=30.0
                )
                
                result = await execute_tool(
                    tool_name="get_stats",
                    services=self.ensure_services(),
                    embedding_manager=self.embedding_manager,
                    arguments={},
                )
                
                response_text = format_tool_response(result, format_type="json")
                return [types.TextContent(type="text", text=response_text)]
                
            except Exception as e:
                error_response = format_error_response(e, include_traceback=self.debug_mode)
                return [types.TextContent(type="text", text=json.dumps(error_response))]

        @self.server.call_tool("health_check")
        async def health_check() -> list[types.TextContent]:
            """Check server health status"""
            # Direct implementation - no routing through _handle_tool_call
            try:
                await asyncio.wait_for(
                    self._initialization_complete.wait(), timeout=30.0
                )
                
                result = await execute_tool(
                    tool_name="health_check",
                    services=self.ensure_services(),
                    embedding_manager=self.embedding_manager,
                    arguments={},
                )
                
                response_text = format_tool_response(result, format_type="json")
                return [types.TextContent(type="text", text=response_text)]
                
            except Exception as e:
                error_response = format_error_response(e, include_traceback=self.debug_mode)
                return [types.TextContent(type="text", text=json.dumps(error_response))]

        @self.server.call_tool("search_regex")
        async def search_regex(
            pattern: str,
            page_size: int = 10,
            offset: int = 0,
            max_response_tokens: int = 20000,
            path: str | None = None,
        ) -> list[types.TextContent]:
            """Search code chunks using regex patterns with pagination support."""
            # Direct implementation - no routing through _handle_tool_call
            try:
                await asyncio.wait_for(
                    self._initialization_complete.wait(), timeout=30.0
                )
                
                args = {
                    "pattern": pattern,
                    "page_size": page_size,
                    "offset": offset,
                    "max_response_tokens": max_response_tokens,
                }
                if path is not None:
                    args["path"] = path
                
                result = await execute_tool(
                    tool_name="search_regex",
                    services=self.ensure_services(),
                    embedding_manager=self.embedding_manager,
                    arguments=parse_mcp_arguments(args),
                )
                
                response_text = format_tool_response(result, format_type="json")
                return [types.TextContent(type="text", text=response_text)]
                
            except Exception as e:
                error_response = format_error_response(e, include_traceback=self.debug_mode)
                return [types.TextContent(type="text", text=json.dumps(error_response))]

        @self.server.call_tool("search_semantic")
        async def search_semantic(
            query: str,
            page_size: int = 10,
            offset: int = 0,
            max_response_tokens: int = 20000,
            path: str | None = None,
            provider: str = "openai",
            model: str = "text-embedding-3-small",
            threshold: float | None = None,
        ) -> list[types.TextContent]:
            """Search code using semantic similarity with pagination support."""
            # Direct implementation - no routing through _handle_tool_call
            try:
                await asyncio.wait_for(
                    self._initialization_complete.wait(), timeout=30.0
                )
                
                args = {
                    "query": query,
                    "page_size": page_size,
                    "offset": offset,
                    "max_response_tokens": max_response_tokens,
                    "provider": provider,
                    "model": model,
                }
                if path is not None:
                    args["path"] = path
                if threshold is not None:
                    args["threshold"] = threshold
                
                result = await execute_tool(
                    tool_name="search_semantic",
                    services=self.ensure_services(),
                    embedding_manager=self.embedding_manager,
                    arguments=parse_mcp_arguments(args),
                )
                
                response_text = format_tool_response(result, format_type="json")
                return [types.TextContent(type="text", text=response_text)]
                
            except Exception as e:
                error_response = format_error_response(e, include_traceback=self.debug_mode)
                return [types.TextContent(type="text", text=json.dumps(error_response))]
            
        self._register_list_tools()

    def _register_list_tools(self) -> None:
        """Register list_tools handler."""
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """List available tools."""
            # Wait for initialization
            try:
                await asyncio.wait_for(
                    self._initialization_complete.wait(), timeout=5.0
                )
            except asyncio.TimeoutError:
                # Return basic tools even if not fully initialized
                pass

            tools = []
            for tool_name, tool in TOOL_REGISTRY.items():
                # Skip embedding-dependent tools if no providers available
                if tool.requires_embeddings and (
                    not self.embedding_manager
                    or not self.embedding_manager.list_providers()
                ):
                    continue

                tools.append(
                    types.Tool(
                        name=tool_name,
                        description=tool.description,
                        inputSchema=tool.parameters,
                    )
                )

            return tools

    @asynccontextmanager
    async def server_lifespan(self) -> AsyncIterator[dict]:
        """Manage server lifecycle with proper initialization and cleanup."""
        try:
            # Initialize services
            await self.initialize()
            self._initialization_complete.set()
            self.debug_log("Server initialization complete")

            # Yield control to server
            yield {"services": self.services, "embeddings": self.embedding_manager}

        finally:
            # Cleanup on shutdown
            await self.cleanup()

    async def run(self) -> None:
        """Run the stdio server with proper lifecycle management."""
        try:
            # Set initialization options with capabilities
            from mcp.server.lowlevel import NotificationOptions
            
            init_options = InitializationOptions(
                server_name="ChunkHound Code Search",
                server_version=__version__,
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )

            # Run with lifespan management
            async with self.server_lifespan():
                # Run the stdio server
                async with mcp.server.stdio.stdio_server() as streams:
                    self.debug_log("Stdio server started, awaiting requests")
                    await self.server.run(
                        streams[0],  # stdin
                        streams[1],  # stdout
                        init_options,
                    )

        except KeyboardInterrupt:
            self.debug_log("Server interrupted by user")
        except Exception as e:
            self.debug_log(f"Server error: {e}")
            if self.debug_mode:
                import traceback

                traceback.print_exc(file=sys.stderr)


async def main(args: Any = None) -> None:
    """Main entry point for the MCP stdio server.
    
    Args:
        args: Pre-parsed arguments. If None, will parse from sys.argv.
    """
    import argparse
    from chunkhound.api.cli.utils.config_factory import create_validated_config
    from chunkhound.mcp.common import add_common_mcp_arguments
    
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
    try:
        server = StdioMCPServer(config, args=args)
        await server.run()
    except Exception as e:
        # CRITICAL: Cannot print to stderr in MCP mode - breaks JSON-RPC protocol
        # Exit silently with error code
        sys.exit(1)


def main_sync() -> None:
    """Synchronous wrapper for CLI entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
