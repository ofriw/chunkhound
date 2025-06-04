"""FastAPI server for ChunkHound search endpoints.

Provides semantic and regex search APIs with NDJSON streaming responses
for coding agent workflows.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from .database import Database
from .embeddings import EmbeddingManager


class SemanticSearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    threshold: Optional[float] = Field(None, ge=0.0, le=2.0, description="Distance threshold")
    provider: str = Field("openai", description="Embedding provider")
    model: str = Field("text-embedding-3-small", description="Embedding model")


class RegexSearchRequest(BaseModel):
    """Request model for regex search."""
    pattern: str = Field(..., description="Regular expression pattern")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")


class SearchResult(BaseModel):
    """Search result model."""
    chunk_id: int
    symbol: str
    start_line: int
    end_line: int
    code: str
    chunk_type: str
    file_path: str
    language: str
    distance: Optional[float] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str


# Global database and embedding manager instances
_database: Optional[Database] = None
_embedding_manager: Optional[EmbeddingManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global _database, _embedding_manager
    
    try:
        # Initialize database and embedding manager
        db_path = Path(os.environ.get("CHUNKHOUND_DB_PATH", Path.home() / ".cache" / "chunkhound" / "chunks.duckdb"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        _database = Database(db_path)
        _database.connect()
        
        _embedding_manager = EmbeddingManager()
        
        # Try to register OpenAI provider as default (optional)
        try:
            from .embeddings import create_openai_provider
            openai_provider = create_openai_provider()
            _embedding_manager.register_provider(openai_provider, set_default=True)
            logger.info("OpenAI embedding provider registered")
        except Exception as e:
            logger.warning(f"Failed to register OpenAI provider: {e}")
            logger.info("API server will run without semantic search capabilities")
        
        logger.info("ChunkHound API server initialized")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize API server: {e}")
        raise
    finally:
        # Cleanup
        if _database:
            _database.close()
        logger.info("ChunkHound API server shutdown")


app = FastAPI(
    title="ChunkHound API",
    description="Local-first semantic code search with vector and regex capabilities",
    version="0.1.0",
    lifespan=lifespan
)


def stream_ndjson(results: List[Dict[str, Any]]) -> str:
    """Convert search results to NDJSON format for streaming."""
    for result in results:
        yield json.dumps(result, ensure_ascii=False) + "\n"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/search/semantic")
async def search_semantic(request: SemanticSearchRequest):
    """Perform semantic search using vector similarity.
    
    Returns results in NDJSON format for streaming consumption by coding agents.
    """
    if not _database:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    if not _embedding_manager or not _embedding_manager.list_providers():
        raise HTTPException(status_code=503, detail="No embedding providers available. Set OPENAI_API_KEY to enable semantic search.")
    
    try:
        # Generate query embedding
        result = await _embedding_manager.embed_texts(
            [request.query], 
            request.provider
        )
        query_vector = result.embeddings[0]
        
        # Perform semantic search
        results = _database.search_semantic(
            query_vector=query_vector,
            provider=request.provider,
            model=request.model,
            limit=request.limit,
            threshold=request.threshold
        )
        
        # Return NDJSON stream
        return StreamingResponse(
            stream_ndjson(results),
            media_type="application/x-ndjson"
        )
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/regex")
async def search_regex(request: RegexSearchRequest):
    """Perform regex search on code content.
    
    Returns results in NDJSON format for streaming consumption by coding agents.
    """
    if not _database:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        # Perform regex search
        results = _database.search_regex(
            pattern=request.pattern,
            limit=request.limit
        )
        
        # Return NDJSON stream
        return StreamingResponse(
            stream_ndjson(results),
            media_type="application/x-ndjson"
        )
        
    except Exception as e:
        logger.error(f"Regex search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/semantic")
async def search_semantic_get(
    query: str = Query(..., description="Search query text"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    threshold: Optional[float] = Query(None, ge=0.0, le=2.0, description="Distance threshold"),
    provider: str = Query("openai", description="Embedding provider"),
    model: str = Query("text-embedding-3-small", description="Embedding model")
):
    """GET endpoint for semantic search (convenience method)."""
    request = SemanticSearchRequest(
        query=query,
        limit=limit,
        threshold=threshold,
        provider=provider,
        model=model
    )
    return await search_semantic(request)


@app.get("/search/regex")
async def search_regex_get(
    pattern: str = Query(..., description="Regular expression pattern"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """GET endpoint for regex search (convenience method)."""
    request = RegexSearchRequest(pattern=pattern, limit=limit)
    return await search_regex(request)


@app.get("/stats")
async def get_stats():
    """Get database statistics."""
    if not _database:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    try:
        stats = _database.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return {"error": "not_found", "message": "Endpoint not found"}


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Server error: {exc}")
    return {"error": "internal_server_error", "message": "Internal server error"}