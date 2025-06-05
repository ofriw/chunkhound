#!/usr/bin/env python3
"""
ChunkHound MCP Server - Model Context Protocol implementation
Provides code search capabilities via stdin/stdout JSON-RPC protocol
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
import sys

# Disable all logging for MCP server to prevent interference with JSON-RPC
logging.disable(logging.CRITICAL)
for logger_name in ['', 'mcp', 'server', 'fastmcp']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

# Disable loguru logger used by database module
try:
    from loguru import logger as loguru_logger
    loguru_logger.remove()
    loguru_logger.add(lambda _: None, level="CRITICAL")
except ImportError:
    pass

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

# Global database and embedding manager instances
_database: Optional[Database] = None
_embedding_manager: Optional[EmbeddingManager] = None

# Initialize MCP server with explicit stdio
server = Server("ChunkHound Code Search")


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    global _database, _embedding_manager
    
    try:
        # Initialize database
        db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        _database = Database(db_path)
        _database.connect()
        
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
        except Exception as e:
            # Silently fail - MCP server will run without semantic search capabilities
            pass
        
        yield {"db": _database, "embeddings": _embedding_manager}
        
    except Exception as e:
        raise Exception(f"Failed to initialize database and embeddings: {e}")
    finally:
        # Cleanup
        if _database:
            try:
                _database.close()
            except Exception:
                pass


def convert_to_ndjson(results: List[Dict[str, Any]]) -> str:
    """Convert search results to NDJSON format."""
    lines = []
    for result in results:
        lines.append(json.dumps(result, ensure_ascii=False))
    return "\n".join(lines)


@server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    if not _database:
        raise Exception("Database not initialized")
    
    if name == "search_regex":
        pattern = arguments.get("pattern", "")
        limit = max(1, min(arguments.get("limit", 10), 100))
        
        try:
            results = _database.search_regex(pattern=pattern, limit=limit)
            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
            raise Exception(f"Search failed: {str(e)}")
    
    elif name == "search_semantic":
        query = arguments.get("query", "")
        limit = max(1, min(arguments.get("limit", 10), 100))
        provider = arguments.get("provider", "openai")
        model = arguments.get("model", "text-embedding-3-small")
        threshold = arguments.get("threshold")
        
        if not _embedding_manager or not _embedding_manager.list_providers():
            raise Exception("No embedding providers available. Set OPENAI_API_KEY to enable semantic search.")
        
        try:
            result = await _embedding_manager.embed_texts([query], provider)
            query_vector = result.embeddings[0]
            
            results = _database.search_semantic(
                query_vector=query_vector,
                provider=provider,
                model=model,
                limit=limit,
                threshold=threshold
            )
            
            return [types.TextContent(type="text", text=convert_to_ndjson(results))]
        except Exception as e:
            raise Exception(f"Semantic search failed: {str(e)}")
    
    elif name == "get_stats":
        try:
            stats = _database.get_stats()
            return [types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False))]
        except Exception as e:
            raise Exception(f"Failed to get stats: {str(e)}")
    
    elif name == "health_check":
        health_status = {
            "status": "healthy",
            "version": "0.1.0",
            "database_connected": _database is not None,
            "embedding_providers": _embedding_manager.list_providers() if _embedding_manager else []
        }
        return [types.TextContent(type="text", text=json.dumps(health_status, ensure_ascii=False))]
    
    else:
        raise ValueError(f"Tool not found: {name}")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="search_regex",
            description="Search code using regular expression patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regular expression pattern to search for"},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (1-100)", "default": 10}
                },
                "required": ["pattern"]
            }
        ),
        types.Tool(
            name="search_semantic",
            description="Search code using semantic similarity (vector search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "limit": {"type": "integer", "description": "Maximum number of results to return (1-100)", "default": 10},
                    "provider": {"type": "string", "description": "Embedding provider to use", "default": "openai"},
                    "model": {"type": "string", "description": "Embedding model to use", "default": "text-embedding-3-small"},
                    "threshold": {"type": "number", "description": "Distance threshold for filtering results (optional)"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_stats",
            description="Get database statistics including file, chunk, and embedding counts",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="health_check",
            description="Check server health status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


async def main():
    """Main entry point for the MCP server using explicit stdio transport."""
    # Use the official MCP Python SDK stdio server pattern
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # Initialize with lifespan context (not used in this implementation but available)
        async with server_lifespan(server) as context:
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ChunkHound Code Search",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


if __name__ == "__main__":
    asyncio.run(main())