#!/usr/bin/env python3
"""
ChunkHound MCP HTTP Server - FastMCP 2.0 implementation
Provides code search capabilities via HTTP transport using FastMCP
"""

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from chunkhound.version import __version__

# Import dependencies (with relative imports fallback)
try:
    from .mcp_server import server_lifespan, _database, _embedding_manager, _initialization_complete
except ImportError:
    from chunkhound.mcp_server import server_lifespan, _database, _embedding_manager, _initialization_complete

# Global context holder
_server_context: dict[str, Any] | None = None


# Initialize FastMCP 2.0 server without complex lifespan for now
mcp = FastMCP("ChunkHound Code Search")


async def ensure_initialization():
    """Ensure ChunkHound components are initialized"""
    global _server_context
    
    if _server_context is not None:
        return
    
    # Import the MCP server class to reuse lifespan
    try:
        from .mcp_server import server
    except ImportError:
        from chunkhound.mcp_server import server
    
    # Initialize server context using existing lifespan
    async with server_lifespan(server) as context:
        _server_context = context
        # Keep the context alive during server operation
        while True:
            await asyncio.sleep(1)


@mcp.tool()
def get_stats() -> dict[str, Any]:
    """Get database statistics including file, chunk, and embedding counts"""
    # Initialize on first call
    if _server_context is None:
        raise Exception("Server not fully initialized yet. Please wait and try again.")
    
    db = _server_context.get("db")
    if not db:
        raise Exception("Database not initialized")
    
    stats = db.get_stats()
    task_coordinator = _server_context.get("task_coordinator")
    if task_coordinator:
        stats["task_coordinator"] = task_coordinator.get_stats()
    
    return stats


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check server health status"""
    health_status = {
        "status": "healthy",
        "version": __version__,
        "database_connected": _server_context is not None and "db" in _server_context,
        "embedding_providers": [],
        "task_coordinator_running": False,
    }
    
    if _server_context:
        embeddings = _server_context.get("embeddings")
        if embeddings:
            health_status["embedding_providers"] = embeddings.list_providers()
        
        task_coordinator = _server_context.get("task_coordinator")
        if task_coordinator:
            health_status["task_coordinator_running"] = task_coordinator.get_stats()["is_running"]
    
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
    # Check initialization
    if _server_context is None:
        raise Exception("Server not fully initialized yet. Please wait and try again.")
    
    db = _server_context.get("db")
    if not db:
        raise Exception("Database not initialized")
    
    # Validate and constrain parameters
    page_size = max(1, min(page_size, 100))
    offset = max(0, offset)
    max_response_tokens = max(1000, min(max_response_tokens, 25000))
    
    # Perform search
    results, pagination = db.search_regex(
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
    # Check initialization
    if _server_context is None:
        raise Exception("Server not fully initialized yet. Please wait and try again.")
    
    db = _server_context.get("db")
    embeddings = _server_context.get("embeddings")
    
    if not db or not embeddings:
        raise Exception("Database or embedding manager not initialized")
    
    if not embeddings.list_providers():
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
            embeddings.embed_texts([query], provider), timeout=12.0
        )
        query_vector = result.embeddings[0]
    except asyncio.TimeoutError:
        raise Exception(
            "Semantic search timed out. This can happen when OpenAI API is experiencing high latency. Please try again."
        )
    
    # Perform search
    results, pagination = db.search_semantic(
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
    
    parser = argparse.ArgumentParser(description="ChunkHound MCP HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Set debug mode
    if args.debug:
        os.environ["CHUNKHOUND_DEBUG"] = "1"
    
    # Set MCP mode to suppress stderr output
    os.environ["CHUNKHOUND_MCP_MODE"] = "1"
    
    # Check if we're in main thread for signal handling
    if not is_main_thread():
        # Running in non-main thread, skip signal setup
        pass
    
    # Run FastMCP with HTTP transport
    mcp.run(
        transport="http",
        host=args.host,
        port=args.port,
        path="/mcp",
    )


if __name__ == "__main__":
    main()