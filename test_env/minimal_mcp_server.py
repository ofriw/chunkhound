#!/usr/bin/env python3
"""
Minimal MCP Server for Isolated Testing

This script creates a standalone MCP server instance for testing realtime
incremental updates without interfering with the main running instance.

Usage:
    python minimal_mcp_server.py

Environment Variables:
    OPENAI_API_KEY - Required for semantic search testing
    TEST_DB_PATH - Optional custom database path (default: ./test_chunks.duckdb)
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from providers.database.duckdb_provider import DuckDBProvider
from services.embedding_service import EmbeddingService
from providers.embeddings.openai_provider import OpenAIEmbeddingProvider

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Global instances
_database: Optional[DuckDBProvider] = None
_embedding_service: Optional[EmbeddingService] = None
_server = Server("chunkhound-test")

async def initialize_services():
    """Initialize database and embedding services for testing."""
    global _database, _embedding_service

    try:
        # Initialize database with test database file
        test_db_path = os.getenv("TEST_DB_PATH", "./test_chunks.duckdb")
        _database = DuckDBProvider(db_path=test_db_path)
        logger.info(f"Database initialized: {test_db_path}")

        # Initialize embedding manager if API key available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            openai_provider = OpenAIEmbeddingProvider(api_key=openai_key)
            _embedding_service = EmbeddingService(_database, openai_provider)
            logger.info("OpenAI embedding service initialized")
        else:
            logger.warning("No OPENAI_API_KEY found - semantic search disabled")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

def convert_to_ndjson(results: List[Dict[str, Any]]) -> str:
    """Convert results to NDJSON format."""
    return '\n'.join(json.dumps(result, ensure_ascii=False) for result in results)

@_server.call_tool()
async def search_semantic(
    query: str,
    limit: int = 10,
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    threshold: Optional[float] = None
) -> List[types.TextContent]:
    """Perform semantic search with comprehensive logging."""
    search_start = time.time()
    logger.info(f"SEARCH_SEMANTIC_START: query='{query}', limit={limit}, provider={provider}, model={model}")

    if not _database:
        raise Exception("Database not initialized")

    if not _embedding_service:
        raise Exception("No embedding providers available. Set OPENAI_API_KEY to enable semantic search.")

    try:
        # Generate embedding
        embed_start = time.time()
        result = await _embedding_service.embed_texts([query], provider)
        query_vector = result.embeddings[0]
        embed_time = time.time() - embed_start
        logger.debug(f"EMBEDDING_TIME: {embed_time:.4f}s for query: '{query}'")

        # Perform search
        db_search_start = time.time()
        results = _database.search_semantic(
            query_vector=query_vector,
            provider=provider,
            model=model,
            limit=limit,
            threshold=threshold
        )
        db_search_time = time.time() - db_search_start
        logger.debug(f"DB_SEARCH_TIME: {db_search_time:.4f}s, found {len(results)} results")

        # Log detailed results
        total_time = time.time() - search_start
        logger.info(f"SEARCH_SEMANTIC_COMPLETE: {len(results)} results in {total_time:.4f}s")
        for i, result in enumerate(results[:3]):  # Log first 3 results
            logger.debug(f"RESULT_{i}: {result.get('file_path', 'unknown')} - {result.get('similarity', 0):.4f}")

        return [types.TextContent(type="text", text=convert_to_ndjson(results))]

    except Exception as e:
        logger.error(f"SEARCH_SEMANTIC_ERROR: {e}")
        raise Exception(f"Semantic search failed: {str(e)}")

@_server.call_tool()
async def search_regex(pattern: str, limit: int = 10) -> List[types.TextContent]:
    """Perform regex search with comprehensive logging."""
    search_start = time.time()
    logger.info(f"SEARCH_REGEX_START: pattern='{pattern}', limit={limit}")

    if not _database:
        raise Exception("Database not initialized")

    try:
        results = _database.search_regex(pattern=pattern, limit=limit)
        search_time = time.time() - search_start

        logger.info(f"SEARCH_REGEX_COMPLETE: {len(results)} results in {search_time:.4f}s")
        for i, result in enumerate(results[:3]):  # Log first 3 results
            logger.debug(f"RESULT_{i}: {result.get('file_path', 'unknown')} - line {result.get('start_line', 0)}")

        return [types.TextContent(type="text", text=convert_to_ndjson(results))]

    except Exception as e:
        logger.error(f"SEARCH_REGEX_ERROR: {e}")
        raise Exception(f"Regex search failed: {str(e)}")

@_server.call_tool()
async def get_stats() -> List[types.TextContent]:
    """Get database statistics with logging."""
    logger.info("GET_STATS_START")

    if not _database:
        raise Exception("Database not initialized")

    try:
        stats = _database.get_stats()
        logger.info(f"GET_STATS_COMPLETE: {stats}")
        return [types.TextContent(type="text", text=json.dumps(stats, ensure_ascii=False))]

    except Exception as e:
        logger.error(f"GET_STATS_ERROR: {e}")
        raise Exception(f"Failed to get stats: {str(e)}")

@_server.call_tool()
async def health_check() -> List[types.TextContent]:
    """Health check with detailed status."""
    logger.info("HEALTH_CHECK_START")

    health_status = {
        "status": "healthy",
        "version": "test-env-1.0",
        "database_connected": _database is not None,
        "database_path": getattr(_database, 'db_path', None) if _database else None,
        "embedding_providers": [provider] if _embedding_service else [],
        "test_mode": True,
        "timestamp": time.time()
    }

    logger.info(f"HEALTH_CHECK_COMPLETE: {health_status}")
    return [types.TextContent(type="text", text=json.dumps(health_status, ensure_ascii=False))]

@_server.call_tool()
async def index_file(file_path: str) -> List[types.TextContent]:
    """Index a single file for testing."""
    index_start = time.time()
    logger.info(f"INDEX_FILE_START: {file_path}")

    if not _database:
        raise Exception("Database not initialized")

    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise Exception(f"File not found: {file_path}")

        # Use incremental processing
        result = await _database.process_file_incremental(file_path_obj)
        index_time = time.time() - index_start

        logger.info(f"INDEX_FILE_COMPLETE: {file_path} in {index_time:.4f}s - {result}")
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    except Exception as e:
        logger.error(f"INDEX_FILE_ERROR: {file_path} - {e}")
        raise Exception(f"Failed to index file: {str(e)}")

@_server.call_tool()
async def delete_file(file_path: str) -> List[types.TextContent]:
    """Delete a file from the index for testing."""
    delete_start = time.time()
    logger.info(f"DELETE_FILE_START: {file_path}")

    if not _database:
        raise Exception("Database not initialized")

    try:
        result = _database.delete_file_completely(file_path)
        delete_time = time.time() - delete_start

        logger.info(f"DELETE_FILE_COMPLETE: {file_path} in {delete_time:.4f}s - {result}")
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    except Exception as e:
        logger.error(f"DELETE_FILE_ERROR: {file_path} - {e}")
        raise Exception(f"Failed to delete file: {str(e)}")

async def main():
    """Main server entry point."""
    logger.info("Starting minimal MCP server for testing...")

    try:
        # Initialize services
        await initialize_services()

        # Start stdio server
        logger.info("MCP server ready for connections")
        async with stdio_server() as (read_stream, write_stream):
            await _server.run(read_stream, write_stream, _server.create_initialization_options())

    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
