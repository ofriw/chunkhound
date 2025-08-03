#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP
"""

import asyncio
import os
import sys
import threading
from typing import Any

from fastmcp import FastMCP

from chunkhound.mcp_shared import add_common_mcp_arguments
from chunkhound.mcp_tools import (
    get_stats_impl,
    health_check_impl,
    limit_response_size,
    search_regex_impl,
    search_semantic_impl,
)

# Import dependencies (with relative imports fallback)
try:
    from .api.cli.utils.config_helpers import validate_config_for_command
    from .core.config.config import Config
    from .embeddings import EmbeddingManager
    from .mcp_common import initialize_mcp_services
except ImportError:
    from chunkhound.api.cli.utils.config_helpers import validate_config_for_command
    from chunkhound.core.config.config import Config
    from chunkhound.embeddings import EmbeddingManager
    from chunkhound.mcp_common import initialize_mcp_services

# Global components - initialized lazily
_services = None
_embedding_manager: EmbeddingManager | None = None
_initialization_lock = None
_config: Config | None = None  # Global to store Config


async def ensure_initialization() -> None:
    """Ensure components are initialized (lazy initialization)"""
    global _services, _embedding_manager, _initialization_lock

    if _services is not None and _embedding_manager is not None:
        return

    # Create lock on first use
    if _initialization_lock is None:
        _initialization_lock = asyncio.Lock()

    async with _initialization_lock:
        if _services is not None and _embedding_manager is not None:
            return

        # Set MCP mode to suppress stderr output that interferes with JSON-RPC
        os.environ["CHUNKHOUND_MCP_MODE"] = "1"

        # Check debug flag from environment
        debug_mode = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")

        try:
            # Load configuration using unified pattern
            # Must match stdio server pattern for consistency
            global _config
            config = _config
            if config:
                debug_mode = config.debug or debug_mode

            # Validate config for MCP usage
            if config:
                validation_errors = validate_config_for_command(config, "mcp")
                if validation_errors and debug_mode:
                    # Log validation errors in debug mode but continue
                    # (HTTP server can work with partial config)
                    for error in validation_errors:
                        print(
                            f"[MCP-HTTP-SERVER] Config validation warning: {error}",
                            file=sys.stderr
                        )

            # Initialize MCP services with validated config
            if not config:
                raise ValueError("Configuration not initialized")
            _services, _embedding_manager, _ = await initialize_mcp_services(
                config, debug_mode
            )

        except Exception as e:
            raise Exception(f"Failed to initialize database and embeddings: {e}")


# Initialize FastMCP 2.0 server
mcp: FastMCP = FastMCP("ChunkHound Code Search")


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """Get database statistics including file, chunk, and embedding counts"""
    await ensure_initialization()

    if not _services:
        raise Exception("Services not initialized")

    # Use shared implementation
    return await get_stats_impl(_services)


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check server health status"""
    await ensure_initialization()

    # Use shared implementation
    if not _services or not _embedding_manager:
        raise Exception("Server components not properly initialized")

    result = await health_check_impl(_services, _embedding_manager)
    return dict(result)


@mcp.tool()
async def search_regex(
    pattern: str,
    page_size: int = 10,
    offset: int = 0,
    max_response_tokens: int = 20000,
    path: str | None = None,
) -> dict[str, Any]:
    """Search code chunks using regex patterns with pagination support."""
    await ensure_initialization()

    if not _services:
        raise Exception("Services not initialized")

    # Use shared implementation
    response_data = await search_regex_impl(
        services=_services,
        pattern=pattern,
        page_size=page_size,
        offset=offset,
        path_filter=path,
    )

    # Apply response size limiting
    limited_response = limit_response_size(response_data)
    return dict(limited_response)


@mcp.tool()
async def search_semantic(
    query: str,
    page_size: int = 10,
    offset: int = 0,
    max_response_tokens: int = 20000,
    provider: str | None = None,
    model: str | None = None,
    threshold: float | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Search code using semantic similarity with pagination support."""
    await ensure_initialization()

    if not _services or not _embedding_manager:
        raise Exception("Services or embedding manager not initialized")

    # Use shared implementation
    response_data = await search_semantic_impl(
        services=_services,
        embedding_manager=_embedding_manager,
        query=query,
        page_size=page_size,
        offset=offset,
        provider=provider,
        model=model,
        threshold=threshold,
        path_filter=path,
    )

    # Apply response size limiting
    limited_response = limit_response_size(response_data)
    return dict(limited_response)


def is_main_thread() -> bool:
    """Check if running in main thread"""
    return threading.current_thread() is threading.main_thread()


def main():
    """Main entry point for HTTP server"""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(
        description="ChunkHound MCP HTTP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Server-specific arguments
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")

    # Add common MCP arguments
    add_common_mcp_arguments(parser)

    args = parser.parse_args()

    # Create and store Config globally for use in ensure_initialization
    global _config
    _config = Config(args=args)

    # Set debug mode
    if args.debug:
        os.environ["CHUNKHOUND_DEBUG"] = "1"

    # Set MCP mode to suppress stderr output
    # os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    # Check if we're in main thread for signal handling
    if not is_main_thread():
        # Running in non-main thread, skip signal setup
        pass

    # Create HTTP app with proper JSON response configuration
    # Safely access MCP config with defaults
    mcp_config = _config.mcp if _config and hasattr(_config, 'mcp') else None
    host = getattr(mcp_config, 'host', "127.0.0.1")
    port = getattr(mcp_config, 'port', 8000)

    print(f"About to start FastMCP server on {host}:{port}", file=sys.stderr)

    # Use the correct FastMCP configuration for JSON responses
    app = mcp.http_app(
        path="/mcp",
        json_response=True,  # Force JSON responses instead of SSE
        stateless_http=True,  # Enable stateless HTTP for proper JSON-RPC
        transport="http",  # Use HTTP transport
    )

    # Run with uvicorn using config values
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
