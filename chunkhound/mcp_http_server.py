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
from chunkhound.version import __version__

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


async def ensure_initialization():
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
            debug_mode = config.debug or debug_mode

            # Validate configuration for MCP HTTP server
            # This ensures same validation as stdio server and CLI
            try:
                # Validate configuration for MCP server
                validation_errors = config.validate_for_command("mcp")
                if validation_errors and debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass
            except Exception:
                if debug_mode:
                    # Non-fatal for HTTP server - continue with config anyway
                    pass

            # Get database path from config
            db_path = Path(config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)


            # Initialize embedding manager
            _embedding_manager = EmbeddingManager()

            # Setup embedding provider (optional - continue if it fails)
            try:
                provider = EmbeddingProviderFactory.create_provider(config.embedding)
                _embedding_manager.register_provider(provider, set_default=True)
            except (ValueError, Exception) as e:
                # API key or configuration issue - continue without embedding provider
                if debug_mode:
                    print(f"Embedding provider setup failed: {e}", file=sys.stderr)

            # Create database using unified factory for consistency with stdio server
            # This ensures same initialization across all MCP servers
            _database = create_database_with_dependencies(
                db_path=db_path,
                config=config,
                embedding_manager=_embedding_manager,
            )

            # Connect to database
            _database.connect()

        except Exception as e:
            raise Exception(f"Failed to initialize database and embeddings: {e}")


# Initialize FastMCP 2.0 server
mcp = FastMCP("ChunkHound Code Search")


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """Get database statistics including file, chunk, and embedding counts"""
    await ensure_initialization()

    if not _database:
        raise Exception("Database not initialized")

    return _database.get_stats()


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check server health status"""
    await ensure_initialization()

    health_status = {
        "status": "healthy",
        "version": __version__,
        "database_connected": _database is not None,
        "embedding_providers": [],
    }

    if _embedding_manager:
        health_status["embedding_providers"] = _embedding_manager.list_providers()

    return health_status


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

    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)
    max_response_tokens = max(1000, min(max_response_tokens, 25000))

    # Perform search
    results, pagination = _database.search_regex(
        pattern=pattern,
        page_size=page_size,
        offset=offset,
        path_filter=path,
    )

    return {"results": results, "pagination": pagination}


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

    if not _embedding_manager.list_providers():
        raise Exception(
            "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
        )

    # Use explicit provider/model from arguments, otherwise get from configured provider
    if not provider or not model:
        try:
            default_provider_obj = _embedding_manager.get_provider()
            if not provider:
                provider = default_provider_obj.name
            if not model:
                model = default_provider_obj.model
        except ValueError:
            raise Exception(
                "No default embedding provider configured. "
                "Either specify provider and model explicitly, or configure a default provider."
            )

    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)
    max_response_tokens = max(1000, min(max_response_tokens, 25000))

    # Get embedding for query
    try:
        result = await asyncio.wait_for(
            _embedding_manager.embed_texts([query], provider), timeout=12.0
        )
        query_vector = result.embeddings[0]
    except asyncio.TimeoutError:
        raise Exception(
            "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
        )

    # Perform search
    results, pagination = _database.search_semantic(
        query_vector=query_vector,
        provider=provider,
        model=model,
        page_size=page_size,
        offset=offset,
        threshold=threshold,
        path_filter=path,
    )

    return {"results": results, "pagination": pagination}


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
    print(f"About to start FastMCP server on {args.host}:{args.port}", file=sys.stderr)

    # Create a new MCP instance for the HTTP app to avoid conflicts with module-level instance
    local_mcp = FastMCP("ChunkHound Code Search")

    # Register the same tools on the new instance
    @local_mcp.tool()
    async def get_stats_local() -> dict[str, Any]:
        """Get database statistics including file, chunk, and embedding counts"""
        await ensure_initialization()

        if not _database:
            raise Exception("Database not initialized")

        return _database.get_stats()

    @local_mcp.tool()
    async def health_check_local() -> dict[str, Any]:
        """Check server health status"""
        await ensure_initialization()

        health_status = {
            "status": "healthy",
            "version": __version__,
            "database_connected": _database is not None,
            "embedding_providers": [],
            }

        if _embedding_manager:
            health_status["embedding_providers"] = _embedding_manager.list_providers()

        return health_status

    @local_mcp.tool()
    async def search_regex_local(
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

        # Validate and constrain parameters
        page_size = max(1, min(page_size, 100))
        offset = max(0, offset)
        max_response_tokens = max(1000, min(max_response_tokens, 25000))

        # Perform search
        results, pagination = _database.search_regex(
            pattern=pattern,
            page_size=page_size,
            offset=offset,
            path_filter=path,
        )

        return {"results": results, "pagination": pagination}

    @local_mcp.tool()
    async def search_semantic_local(
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

        if not _embedding_manager.list_providers():
            raise Exception(
                "No embedding providers available. Set OPENAI_API_KEY to enable semantic search."
            )

        # Use explicit provider/model from arguments, otherwise get from configured provider
        if not provider or not model:
            try:
                default_provider_obj = _embedding_manager.get_provider()
                if not provider:
                    provider = default_provider_obj.name
                if not model:
                    model = default_provider_obj.model
            except ValueError:
                raise Exception(
                    "No default embedding provider configured. "
                    "Either specify provider and model explicitly, or configure a default provider."
                )

        # Validate and constrain parameters
        page_size = max(1, min(page_size, 100))
        offset = max(0, offset)
        max_response_tokens = max(1000, min(max_response_tokens, 25000))

        # Get embedding for query
        try:
            result = await asyncio.wait_for(
                _embedding_manager.embed_texts([query], provider), timeout=12.0
            )
            query_vector = result.embeddings[0]
        except asyncio.TimeoutError:
            raise Exception(
                "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
            )

        # Perform search
        results, pagination = _database.search_semantic(
            query_vector=query_vector,
            provider=provider,
            model=model,
            page_size=page_size,
            offset=offset,
            threshold=threshold,
            path_filter=path,
        )

        return {"results": results, "pagination": pagination}

    # Use the correct FastMCP configuration for JSON responses
    app = local_mcp.http_app(
        path="/mcp",
        json_response=True,      # Force JSON responses instead of SSE
        stateless_http=True,     # Enable stateless HTTP for proper JSON-RPC
        transport="http"         # Use HTTP transport
    )

    # Run with uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
