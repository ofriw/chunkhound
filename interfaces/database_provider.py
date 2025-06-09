"""DatabaseProvider protocol for ChunkHound - abstract interface for database implementations."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Protocol

from core.models import File, Chunk, Embedding, EmbeddingResult
from core.types import ChunkType, Language, FilePath, FileId, ChunkId, Timestamp


class DatabaseProvider(Protocol):
    """Abstract protocol for database providers.
    
    Defines the interface that all database implementations must follow.
    This enables pluggable database backends (DuckDB, PostgreSQL, SQLite, etc.)
    """
    
    @property
    def db_path(self) -> Union[Path, str]:
        """Database connection path or identifier."""
        ...
    
    @property
    def is_connected(self) -> bool:
        """Check if database connection is active."""
        ...
    
    # Connection Management
    def connect(self) -> None:
        """Establish database connection and initialize schema."""
        ...
    
    def disconnect(self) -> None:
        """Close database connection and cleanup resources."""
        ...
    
    # Schema Management
    def create_schema(self) -> None:
        """Create database schema for files, chunks, and embeddings."""
        ...
    
    def create_indexes(self) -> None:
        """Create database indexes for performance optimization."""
        ...
    
    def create_vector_index(self, provider: str, model: str, dims: int, metric: str = "cosine") -> None:
        """Create vector index for specific provider/model/dims combination."""
        ...
    
    def drop_vector_index(self, provider: str, model: str, dims: int, metric: str = "cosine") -> str:
        """Drop vector index for specific provider/model/dims combination."""
        ...
    
    # File Operations
    def insert_file(self, file: File) -> int:
        """Insert file record and return file ID."""
        ...
    
    def get_file_by_path(self, path: str, as_model: bool = False) -> Optional[Union[Dict[str, Any], File]]:
        """Get file record by path."""
        ...
    
    def get_file_by_id(self, file_id: int, as_model: bool = False) -> Optional[Union[Dict[str, Any], File]]:
        """Get file record by ID."""
        ...
    
    def update_file(self, file_id: int, **kwargs) -> None:
        """Update file record with new values."""
        ...
    
    def delete_file_completely(self, file_path: str) -> bool:
        """Delete a file and all its chunks/embeddings completely."""
        ...
    
    # Chunk Operations
    def insert_chunk(self, chunk: Chunk) -> int:
        """Insert chunk record and return chunk ID."""
        ...
    
    def insert_chunks_batch(self, chunks: List[Chunk]) -> List[int]:
        """Insert multiple chunks in batch and return chunk IDs."""
        ...
    
    def get_chunk_by_id(self, chunk_id: int, as_model: bool = False) -> Optional[Union[Dict[str, Any], Chunk]]:
        """Get chunk record by ID."""
        ...
    
    def get_chunks_by_file_id(self, file_id: int, as_model: bool = False) -> List[Union[Dict[str, Any], Chunk]]:
        """Get all chunks for a specific file."""
        ...
    
    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file."""
        ...
    
    def update_chunk(self, chunk_id: int, **kwargs) -> None:
        """Update chunk record with new values."""
        ...
    
    # Embedding Operations
    def insert_embedding(self, embedding: Embedding) -> int:
        """Insert embedding record and return embedding ID."""
        ...
    
    def insert_embeddings_batch(self, embeddings_data: List[Dict]) -> int:
        """Insert multiple embedding vectors with optimization."""
        ...
    
    def get_embedding_by_chunk_id(self, chunk_id: int, provider: str, model: str) -> Optional[Embedding]:
        """Get embedding for specific chunk, provider, and model."""
        ...
    
    def get_existing_embeddings(self, chunk_ids: List[int], provider: str, model: str) -> Set[int]:
        """Get set of chunk IDs that already have embeddings for given provider/model."""
        ...
    
    def delete_embeddings_by_chunk_id(self, chunk_id: int) -> None:
        """Delete all embeddings for a specific chunk."""
        ...
    
    # Search Operations
    def search_semantic(
        self, 
        query_embedding: List[float], 
        provider: str, 
        model: str, 
        limit: int = 10,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Perform semantic vector search."""
        ...
    
    def search_regex(self, pattern: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform regex search on code content."""
        ...
    
    def search_text(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform full-text search on code content."""
        ...
    
    # Statistics and Monitoring
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics (file count, chunk count, etc.)."""
        ...
    
    def get_file_stats(self, file_id: int) -> Dict[str, Any]:
        """Get statistics for a specific file."""
        ...
    
    def get_provider_stats(self, provider: str, model: str) -> Dict[str, Any]:
        """Get statistics for a specific embedding provider/model."""
        ...
    
    # Transaction and Bulk Operations
    def execute_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        ...
    
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        ...
    
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        ...
    
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        ...
    
    # File Processing Integration
    async def process_file(self, file_path: Path, skip_embeddings: bool = False) -> Dict[str, Any]:
        """Process a file end-to-end: parse, chunk, and store in database."""
        ...
    
    async def process_file_incremental(self, file_path: Path) -> Dict[str, Any]:
        """Process a file with incremental parsing and differential chunking."""
        ...
    
    async def process_directory(
        self, 
        directory: Path, 
        patterns: Optional[List[str]] = None, 
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Process all supported files in a directory."""
        ...
    
    # Health and Diagnostics
    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status information."""
        ...
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about the database connection."""
        ...