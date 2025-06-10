"""Database module for ChunkHound - Service layer delegation wrapper.

This is a compatibility wrapper that delegates operations to the new modular service layer.
The original monolithic Database class (2055 lines) has been moved to database_legacy.py.
This new implementation reduces the Database class to ~150 lines by delegating to:
- DuckDBProvider for database operations
- IndexingCoordinator for file processing workflows  
- SearchService for semantic and regex search
- EmbeddingService for vector operations

This maintains backward compatibility while using the new modular architecture.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

# Registry import for service layer
from registry import get_registry, create_indexing_coordinator, create_search_service, create_embedding_service

# Provider imports
from providers.database.duckdb_provider import DuckDBProvider

# Legacy imports for backward compatibility
from .embeddings import EmbeddingManager
from .chunker import Chunker, IncrementalChunker
from .file_discovery_cache import FileDiscoveryCache


class Database:
    """Database connection manager - delegates to service layer.
    
    This is a compatibility wrapper that maintains the original Database API
    while delegating operations to the new modular service layer architecture.
    """

    def __init__(self, db_path: Union[Path, str], embedding_manager: Optional[EmbeddingManager] = None):
        """Initialize database connection and service layer.

        Args:
            db_path: Path to DuckDB database file or ":memory:" for in-memory database
            embedding_manager: Optional embedding manager for vector generation
        """
        self._db_path = db_path
        self.embedding_manager = embedding_manager
        
        # Initialize service layer via registry
        self._provider = DuckDBProvider(db_path, embedding_manager)
        
        # Configure registry with database provider
        registry = get_registry()
        registry.register_provider("database", lambda: self._provider, singleton=True)
        
        # Create services via registry (includes language parser setup)
        self._indexing_coordinator = create_indexing_coordinator()
        self._search_service = create_search_service()
        self._embedding_service = create_embedding_service()
        
        # Legacy compatibility: expose provider connection as self.connection
        self.connection = None  # Will be set after connect()
        
        # Legacy compatibility: shared chunker instances
        self._chunker: Optional[Chunker] = None
        self._incremental_chunker: Optional[IncrementalChunker] = None
        self._file_discovery_cache = FileDiscoveryCache()

    def connect(self) -> None:
        """Connect to DuckDB and load required extensions."""
        logger.info(f"Connecting to database via service layer: {self.db_path}")
        
        # Connect via provider
        self._provider.connect()
        
        # Expose connection for legacy compatibility
        self.connection = self._provider.connection
        
        # Initialize legacy shared instances for backward compatibility
        if not self._chunker:
            self._chunker = Chunker()
            
        if not self._incremental_chunker:
            self._incremental_chunker = IncrementalChunker()
        
        logger.info("✅ Database connected via service layer")

    def close(self) -> None:
        """Close database connection."""
        if self._provider.is_connected:
            self._provider.disconnect()
        self.connection = None

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._provider.is_connected

    # =============================================================================
    # File Processing Methods - Delegate to IndexingCoordinator
    # =============================================================================

    async def process_file(self, file_path: Path, skip_embeddings: bool = False) -> Dict[str, Any]:
        """Process a file end-to-end: parse, chunk, and store in database.
        
        Delegates to IndexingCoordinator for actual processing.
        """
        return await self._indexing_coordinator.process_file(file_path, skip_embeddings)

    async def process_file_incremental(self, file_path: Path) -> Dict[str, Any]:
        """Process a file with incremental parsing and differential chunking.
        
        Note: True incremental processing not yet implemented in service layer.
        This delegates to the provider's incremental processing method.
        """
        return await self._provider.process_file_incremental(file_path)

    async def process_directory(self, directory: Path, patterns: Optional[List[str]] = None, exclude_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process all supported files in a directory.
        
        Delegates to IndexingCoordinator for actual processing.
        """
        if patterns is None:
            patterns = ["**/*.py", "**/*.java", "**/*.cs", "**/*.ts", "**/*.js", "**/*.tsx", "**/*.jsx", "**/*.md", "**/*.markdown"]
        
        return await self._indexing_coordinator.process_directory(directory, patterns, exclude_patterns)

    # =============================================================================
    # Search Methods - Delegate to SearchService
    # =============================================================================

    def search_semantic(self, query_vector: List[float], provider: str, model: str, limit: int = 10, threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Perform semantic similarity search.
        
        Delegates to provider for actual search.
        """
        return self._provider.search_semantic(
            query_embedding=query_vector,
            provider=provider,
            model=model, 
            limit=limit,
            threshold=threshold
        )

    def search_regex(self, pattern: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search code chunks using regex pattern.
        
        Delegates to SearchService for actual search.
        """
        return self._search_service.search_regex(pattern=pattern, limit=limit)

    # =============================================================================
    # Database Operations - Delegate to Provider
    # =============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self._provider.get_stats()

    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file record by path."""
        result = self._provider.get_file_by_path(file_path, as_model=False)
        return result if isinstance(result, dict) else None

    def insert_file(self, file_or_path: Union[str, dict], mtime: Optional[float] = None, 
                   language: Optional[str] = None, size_bytes: Optional[int] = None) -> int:
        """Insert a new file record."""
        # Import here to avoid circular dependency
        from core.models import File
        from core.types import Language, FilePath, Timestamp
        
        if isinstance(file_or_path, str):
            file_model = File(
                path=FilePath(file_or_path),
                mtime=Timestamp(mtime or 0.0),
                language=Language.from_string(language or "unknown"),
                size_bytes=size_bytes or 0
            )
        else:
            # Legacy dict format
            file_model = File(
                path=FilePath(file_or_path["path"]),
                mtime=Timestamp(file_or_path["mtime"]),
                language=Language.from_string(file_or_path["language"]),
                size_bytes=file_or_path["size_bytes"]
            )
        return self._provider.insert_file(file_model)

    def insert_chunk(self, chunk_or_file_id: Union[int, dict], symbol: Optional[str] = None, 
                    start_line: Optional[int] = None, end_line: Optional[int] = None, 
                    code: Optional[str] = None, chunk_type: Optional[str] = None, 
                    language_info: Optional[str] = None, parent_header: Optional[str] = None) -> int:
        """Insert a new chunk record."""
        # Import here to avoid circular dependency
        from core.models import Chunk
        from core.types import ChunkType, Language, FileId, LineNumber
        
        if isinstance(chunk_or_file_id, int):
            chunk_model = Chunk(
                file_id=FileId(chunk_or_file_id),
                symbol=symbol or "",
                start_line=LineNumber(start_line or 0),
                end_line=LineNumber(end_line or 0),
                code=code or "",
                chunk_type=ChunkType.from_string(chunk_type or "unknown"),
                language=Language.from_string(language_info or "unknown"),
                parent_header=parent_header
            )
        else:
            # Legacy dict format
            chunk = chunk_or_file_id
            chunk_model = Chunk(
                file_id=FileId(chunk["file_id"]),
                symbol=chunk["symbol"],
                start_line=LineNumber(chunk["start_line"]),
                end_line=LineNumber(chunk["end_line"]),
                code=chunk["code"],
                chunk_type=ChunkType.from_string(chunk["chunk_type"]),
                language=Language.from_string(chunk.get("language_info", "unknown")),
                parent_header=chunk.get("parent_header")
            )
        return self._provider.insert_chunk(chunk_model)

    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file."""
        from core.types import FileId
        self._provider.delete_file_chunks(FileId(file_id))

    def update_file(self, file_id: int, size_bytes: int, mtime: float) -> None:
        """Update file metadata."""
        self._provider.update_file(file_id, size_bytes=size_bytes, mtime=mtime)

    def delete_file_completely(self, file_path: str) -> bool:
        """Delete a file and all its chunks/embeddings completely.
        
        Args:
            file_path: Path to file to delete completely
            
        Returns:
            True if deletion successful, False otherwise
        """
        return self._provider.delete_file_completely(file_path)

    def get_chunks_by_file_id(self, file_id: int) -> List[Dict[str, Any]]:
        """Get chunks for a specific file."""
        results = self._provider.get_chunks_by_file_id(file_id, as_model=False)
        # Ensure we return Dict objects, not Chunk models
        return [result for result in results if isinstance(result, dict)]

    # =============================================================================
    # Process Coordination Methods - Legacy Support
    # =============================================================================

    def detach_database(self) -> bool:
        """Detach database for coordination with other processes."""
        try:
            # Just disconnect for now
            self._provider.disconnect()
            self.connection = None
            return True
        except Exception as e:
            logger.error(f"Failed to detach database: {e}")
            return False

    def reattach_database(self) -> bool:
        """Reattach database after coordination."""
        try:
            # Reconnect
            self._provider.connect()
            self.connection = self._provider.connection
            return True
        except Exception as e:
            logger.error(f"Failed to reattach database: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect database for coordination."""
        try:
            self._provider.disconnect()
            self.connection = None
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect database: {e}")
            return False

    def reconnect(self) -> bool:
        """Reconnect database after coordination."""
        try:
            self._provider.connect()
            self.connection = self._provider.connection
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect database: {e}")
            return False

    # =============================================================================
    # Health Check
    # =============================================================================

    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        return self._provider.health_check()

    # =============================================================================
    # Legacy Compatibility Properties
    # =============================================================================

    # Legacy compatibility - expose db_path as attribute
    @property
    def db_path(self) -> Union[Path, str]:
        """Get database path."""
        return self._db_path

    def get_file_discovery_cache_stats(self) -> Dict[str, Any]:
        """Get file discovery cache statistics."""
        return self._file_discovery_cache.get_stats()