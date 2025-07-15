#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP
"""

import asyncio
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from chunkhound.version import __version__

# Import dependencies (with relative imports fallback)
try:
    from .database import Database
    from .embeddings import EmbeddingManager
except ImportError:
    from chunkhound.database import Database
    from chunkhound.embeddings import EmbeddingManager

# Global components - initialized lazily
_database: Database | None = None
_embedding_manager: EmbeddingManager | None = None
_initialization_lock = asyncio.Lock()


async def ensure_initialization():
    """Ensure components are initialized (lazy initialization)"""
    global _database, _embedding_manager
    
    if _database is not None and _embedding_manager is not None:
        return
    
    async with _initialization_lock:
        if _database is not None and _embedding_manager is not None:
            return
        
        # Skip database initialization for now to avoid hanging
        # This allows the server to start and respond to handshake
        # Tools will fail with proper error messages
        pass


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
        "task_coordinator_running": False,
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
    provider: str = "openai",
    model: str = "text-embedding-3-small",
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
    
    parser = argparse.ArgumentParser(description="ChunkHound MCP HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
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
    
    # Use the correct FastMCP configuration for JSON responses
    app = mcp.http_app(
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
        log_level="info" if args.debug else "warning"
    )


if __name__ == "__main__":
    main()