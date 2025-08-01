#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP
"""

import asyncio
import os
import sys
import threading
from pathlib import Path
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
    from .core.config import EmbeddingProviderFactory
    from .core.config.config import Config
    from .database import Database
    from .database_factory import create_database_with_dependencies
    from .embeddings import EmbeddingManager
except ImportError:
    from chunkhound.core.config import EmbeddingProviderFactory
    from chunkhound.core.config.config import Config
    from chunkhound.database import Database
    from chunkhound.database_factory import create_database_with_dependencies
    from chunkhound.embeddings import EmbeddingManager

# Global components - initialized lazily
_database: Database | None = None
_embedding_manager: EmbeddingManager | None = None
_initialization_lock = None
_config: Config | None = None  # Global to store Config


async def ensure_initialization() -> None:
    """Ensure components are initialized (lazy initialization)"""
    global _database, _embedding_manager, _initialization_lock

    if _database is not None and _embedding_manager is not None:
        return

    # Create lock on first use
    if _initialization_lock is None:
        _initialization_lock = asyncio.Lock()

    async with _initialization_lock:
        if _database is not None and _embedding_manager is not None:
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

            # Validate configuration for MCP HTTP server
            # This ensures same validation as stdio server and CLI
            try:
                # Validate configuration for MCP server
                if config:
                    validation_errors = config.validate_for_command("mcp")
                else:
                    validation_errors = []
                if validation_errors and debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass
            except Exception:
                if debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass

            # Get database path from config
            if not config:
                raise ValueError("Configuration not initialized")
            if not config or not config.database:
                raise ValueError("Database configuration not initialized")
            db_path = Path(config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Initialize embedding manager
            _embedding_manager = EmbeddingManager()

            # Setup embedding provider (optional - continue if it fails)
            try:
                if config.embedding:
                    provider = EmbeddingProviderFactory.create_provider(config.embedding)
                else:
                    raise ValueError("No embedding configuration available")
                _embedding_manager.register_provider(provider, set_default=True)
            except (ValueError, Exception) as e:
                # API key or configuration issue - continue without embedding provider
                if debug_mode:
                    print(f"Embedding provider setup failed: {e}", file=sys.stderr)

            # Create database using unified factory for consistency with stdio server
            # This ensures same initialization across all MCP servers
            _database = create_database_with_dependencies(
                db_path=db_path,
                config=config.to_dict(),
                embedding_manager=_embedding_manager,
            )

            # Connect to database
            _database.connect()

        except Exception as e:
            raise Exception(f"Failed to initialize database and embeddings: {e}")


# Initialize FastMCP 2.0 server
mcp: FastMCP = FastMCP("ChunkHound Code Search")


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """Get database statistics including file, chunk, and embedding counts"""
    await ensure_initialization()

    if not _database:
        raise Exception("Database not initialized")

    # Use shared implementation
    return await get_stats_impl(_database)


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check server health status"""
    await ensure_initialization()

    # Use shared implementation
    if not _database or not _embedding_manager:
        raise Exception("Server components not properly initialized")

    result = await health_check_impl(_database, _embedding_manager)
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

    if not _database:
        raise Exception("Database not initialized")

    # Use shared implementation
    response_data = await search_regex_impl(
        database=_database,
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

    if not _database or not _embedding_manager:
        raise Exception("Database or embedding manager not initialized")

    # Use shared implementation
    response_data = await search_semantic_impl(
        database=_database,
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
    print(f"About to start FastMCP server on {_config.mcp.host}:{_config.mcp.port}", file=sys.stderr)

    # Use the correct FastMCP configuration for JSON responses
    app = mcp.http_app(
        path="/mcp",
        json_response=True,  # Force JSON responses instead of SSE
        stateless_http=True,  # Enable stateless HTTP for proper JSON-RPC
        transport="http",  # Use HTTP transport
    )

    # Run with uvicorn using config values instead of raw args
    uvicorn.run(app, host=_config.mcp.host, port=_config.mcp.port, log_level="info")


if __name__ == "__main__":
    main()
