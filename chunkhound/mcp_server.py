#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from loguru import logger

try:
    from .database import Database
    from .embeddings import EmbeddingManager
except ImportError:
    # Handle running as standalone script
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from database import Database
    from embeddings import EmbeddingManager

# Initialize FastMCP server
mcp = FastMCP("ChunkHound Code Search")

# Global database and embedding manager instances
_database: Optional[Database] = None
_embedding_manager: Optional[EmbeddingManager] = None


def initialize_database_and_embeddings():
    """Initialize database and embedding manager (similar to FastAPI lifespan)"""
    global _database, _embedding_manager
    
    try:
        # Initialize database
        db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        _database = Database(db_path)
        _database.connect()
        logger.info(f"Database connected: {db_path}")
        
        # Initialize embedding manager
        _embedding_manager = EmbeddingManager()
        
        # Try to register OpenAI provider as default (optional)
        try:
            try:
                from .embeddings import create_openai_provider
            except ImportError:
                from embeddings import create_openai_provider
            openai_provider = create_openai_provider()
            _embedding_manager.register_provider(openai_provider, set_default=True)
            logger.info("OpenAI embedding provider registered")
        except Exception as e:
            logger.warning(f"Failed to register OpenAI provider: {e}")
            logger.info("MCP server will run without semantic search capabilities")
            
    except Exception as e:
        logger.error(f"Failed to initialize database and embeddings: {e}")
        raise


def convert_to_ndjson(results: List[Dict[str, Any]]) -> str:
    """Convert search results to NDJSON format."""
    lines = []
    for result in results:
        lines.append(json.dumps(result, ensure_ascii=False))
    return "\n".join(lines)


@mcp.tool()
def search_regex(pattern: str, limit: int = 10) -> str:
    """Search code using regular expression patterns.
    
    Args:
        pattern: Regular expression pattern to search for
        limit: Maximum number of results to return (1-100)
        
    Returns:
        NDJSON formatted search results
    """
    if not _database:
        raise Exception("Database not initialized")
    
    # Validate limit
    limit = max(1, min(limit, 100))
    
    try:
        # Perform regex search
        results = _database.search_regex(
            pattern=pattern,
            limit=limit
        )
        
        # Convert to NDJSON format
        return convert_to_ndjson(results)
        
    except Exception as e:
        logger.error(f"Regex search failed: {e}")
        raise Exception(f"Search failed: {str(e)}")


@mcp.tool()
def search_semantic(query: str, limit: int = 10, provider: str = "openai", model: str = "text-embedding-3-small", threshold: Optional[float] = None) -> str:
    """Search code using semantic similarity (vector search).
    
    Args:
        query: Natural language search query
        limit: Maximum number of results to return (1-100)
        provider: Embedding provider to use (default: openai)
        model: Embedding model to use (default: text-embedding-3-small)
        threshold: Distance threshold for filtering results (optional)
        
    Returns:
        NDJSON formatted search results
    """
    if not _database:
        raise Exception("Database not initialized")
    
    if not _embedding_manager or not _embedding_manager.list_providers():
        raise Exception("No embedding providers available. Set OPENAI_API_KEY to enable semantic search.")
    
    # Validate limit
    limit = max(1, min(limit, 100))
    
    try:
        # Generate query embedding (run async function in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _embedding_manager.embed_texts([query], provider)
            )
            query_vector = result.embeddings[0]
        finally:
            loop.close()
        
        # Perform semantic search
        results = _database.search_semantic(
            query_vector=query_vector,
            provider=provider,
            model=model,
            limit=limit,
            threshold=threshold
        )
        
        # Convert to NDJSON format
        return convert_to_ndjson(results)
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise Exception(f"Semantic search failed: {str(e)}")


@mcp.tool()
def get_stats() -> str:
    """Get database statistics including file, chunk, and embedding counts.
    
    Returns:
        JSON formatted statistics
    """
    if not _database:
        raise Exception("Database not initialized")
    
    try:
        stats = _database.get_stats()
        return json.dumps(stats, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise Exception(f"Failed to get stats: {str(e)}")


@mcp.tool()
def health_check() -> str:
    """Check server health status.
    
    Returns:
        JSON formatted health status
    """
    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "database_connected": _database is not None,
        "embedding_providers": _embedding_manager.list_providers() if _embedding_manager else []
    }
    return json.dumps(health_status, ensure_ascii=False)


def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize database and embeddings
        initialize_database_and_embeddings()
        
        # Start MCP server
        logger.info("Starting ChunkHound MCP Server")
        mcp.run()  # Uses STDIO transport by default
        
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        raise
    finally:
        # Cleanup
        if _database:
            try:
                _database.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")


if __name__ == "__main__":
    main()