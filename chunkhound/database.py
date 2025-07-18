"""Database module for ChunkHound - Service layer delegation wrapper.

This is a compatibility wrapper that delegates operations to the new modular
service layer.
The original monolithic Database class (2055 lines) has been moved to
database_legacy.py.
This new implementation reduces the Database class to ~150 lines by delegating to:
- DuckDBProvider for database operations
- IndexingCoordinator for file processing workflows
- SearchService for semantic and regex search
- EmbeddingService for vector operations

This maintains backward compatibility while using the new modular architecture.
"""

import threading
from pathlib import Path

# Service imports for type hints only
from typing import TYPE_CHECKING, Any

from loguru import logger

from chunkhound.core.config.unified_config import DatabaseConfig

# Core imports
from chunkhound.core.types.common import Language

if TYPE_CHECKING:
    from chunkhound.services.embedding_service import EmbeddingService
    from chunkhound.services.indexing_coordinator import IndexingCoordinator
    from chunkhound.services.search_service import SearchService

# Provider imports
# Registry import for service layer
from chunkhound.registry import (
    create_embedding_service,
    create_indexing_coordinator,
    create_search_service,
    get_registry,
)

from .chunker import Chunker, IncrementalChunker

# Legacy imports for backward compatibility
from .embeddings import EmbeddingManager
from .file_discovery_cache import FileDiscoveryCache


class Database:
    """Database connection manager - delegates to service layer.

    This is a compatibility wrapper that maintains the original Database API
    while delegating operations to the new modular service layer architecture.
    """

    def __init__(
        self,
        db_path: Path | str,
        embedding_manager: EmbeddingManager | None = None,
        config: DatabaseConfig | None = None,
        indexing_coordinator: "IndexingCoordinator | None" = None,
        search_service: "SearchService | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        provider: Any | None = None,
    ):
        """Initialize database connection and service layer.

        Args:
            db_path: Path to database file or ":memory:" for in-memory database
            embedding_manager: Optional embedding manager for vector generation
            config: Optional database configuration (auto-detected if not provided)
            indexing_coordinator: Pre-configured IndexingCoordinator (recommended)
            search_service: Pre-configured SearchService (recommended)
            embedding_service: Pre-configured EmbeddingService (recommended)
            provider: Pre-configured database provider (recommended)
        """
        self._db_path = db_path
        self.embedding_manager = embedding_manager

        # Connection synchronization lock
        self._connection_lock = threading.RLock()

        # Use injected dependencies if provided (preferred path)
        if indexing_coordinator and search_service and embedding_service and provider:
            self._indexing_coordinator = indexing_coordinator
            self._search_service = search_service
            self._embedding_service = embedding_service
            self._provider = provider
        else:
            # Legacy path: Auto-configure (deprecated, use create_database_with_dependencies)
            logger.warning(
                "Using legacy Database initialization - consider using create_database_with_dependencies()"
            )

            # Auto-detect configuration if not provided
            if config is None:
                from chunkhound.core.config.unified_config import ChunkHoundConfig

                try:
                    unified_config = ChunkHoundConfig.load_hierarchical()
                    config = unified_config.database
                except Exception:
                    # Fallback to default configuration
                    config = DatabaseConfig()

            # Check if registry is already configured with a database provider
            registry = get_registry()
            try:
                existing_provider = registry.get_provider("database")
                self._provider = existing_provider
                self._indexing_coordinator = create_indexing_coordinator()
                self._search_service = create_search_service()
                self._embedding_service = create_embedding_service()
            except ValueError:
                # Initialize service layer via registry using factory
                from chunkhound.providers.database_factory import (
                    DatabaseProviderFactory,
                )

                self._provider = DatabaseProviderFactory.create_provider(
                    config, embedding_manager
                )

                # Register the new provider
                registry.register_provider(
                    "database", lambda: self._provider, singleton=True
                )

                # Create services via registry (includes language parser setup)
                self._indexing_coordinator = create_indexing_coordinator()
                self._search_service = create_search_service()
                self._embedding_service = create_embedding_service()

        # Legacy compatibility: expose provider connection as self.connection
        self.connection = None  # Will be set after connect()

        # Legacy compatibility: shared chunker instances
        self._chunker: Chunker | None = None
        self._incremental_chunker: IncrementalChunker | None = None
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
        with self._connection_lock:
            if self._provider.is_connected:
                self._provider.disconnect()
            self.connection = None

    def is_connected(self) -> bool:
        """Check if database is connected."""
        with self._connection_lock:
            return self._provider.is_connected

    # =============================================================================
    # File Processing Methods - Delegate to IndexingCoordinator
    # =============================================================================

    async def process_file(
        self, file_path: Path, skip_embeddings: bool = False
    ) -> dict[str, Any]:
        """Process a file end-to-end: parse, chunk, and store in database.

        Delegates to IndexingCoordinator for actual processing.
        """
        return await self._indexing_coordinator.process_file(file_path, skip_embeddings)

    async def process_directory(
        self,
        directory: Path,
        patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Process all supported files in a directory.

        Delegates to IndexingCoordinator for actual processing.
        """
        if patterns is None:
            # Use centralized file patterns from Language enum
            patterns = Language.get_file_patterns()

        return await self._indexing_coordinator.process_directory(
            directory, patterns, exclude_patterns
        )

    # =============================================================================
    # Search Methods - Delegate to SearchService
    # =============================================================================

    def search_semantic(
        self,
        query_vector: list[float],
        provider: str,
        model: str,
        page_size: int = 10,
        offset: int = 0,
        threshold: float | None = None,
        path_filter: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform semantic similarity search.

        Delegates to provider for actual search.
        """
        return self._provider.search_semantic(
            query_embedding=query_vector,
            provider=provider,
            model=model,
            page_size=page_size,
            offset=offset,
            threshold=threshold,
            path_filter=path_filter,
        )

    def search_regex(
        self,
        pattern: str,
        page_size: int = 10,
        offset: int = 0,
        path_filter: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Search code chunks using regex pattern.

        Delegates to provider for actual search.
        """
        return self._provider.search_regex(
            pattern=pattern, page_size=page_size, offset=offset, path_filter=path_filter
        )

    # =============================================================================
    # Database Operations - Delegate to Provider
    # =============================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        return self._provider.get_stats()

    def get_file_by_path(self, file_path: str) -> dict[str, Any] | None:
        """Get file record by path."""
        result = self._provider.get_file_by_path(file_path, as_model=False)
        return result if isinstance(result, dict) else None

    def insert_file(
        self,
        file_or_path: str | dict,
        mtime: float | None = None,
        language: str | None = None,
        size_bytes: int | None = None,
    ) -> int:
        """Insert a new file record."""
        # Import here to avoid circular dependency
        from chunkhound.core.models import File
        from chunkhound.core.types.common import FilePath, Language, Timestamp

        if isinstance(file_or_path, str):
            file_model = File(
                path=FilePath(file_or_path),
                mtime=Timestamp(mtime or 0.0),
                language=Language.from_string(language or "unknown"),
                size_bytes=size_bytes or 0,
            )
        else:
            # Legacy dict format
            file_model = File(
                path=FilePath(file_or_path["path"]),
                mtime=Timestamp(file_or_path["mtime"]),
                language=Language.from_string(file_or_path["language"]),
                size_bytes=file_or_path["size_bytes"],
            )
        return self._provider.insert_file(file_model)

    def insert_chunk(
        self,
        chunk_or_file_id: int | dict,
        symbol: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        code: str | None = None,
        chunk_type: str | None = None,
        language_info: str | None = None,
        parent_header: str | None = None,
    ) -> int:
        """Insert a new chunk record."""
        # Import here to avoid circular dependency
        from chunkhound.core.models import Chunk
        from chunkhound.core.types.common import ChunkType, FileId, Language, LineNumber

        if isinstance(chunk_or_file_id, int):
            chunk_model = Chunk(
                file_id=FileId(chunk_or_file_id),
                symbol=symbol or "",
                start_line=LineNumber(start_line or 0),
                end_line=LineNumber(end_line or 0),
                code=code or "",
                chunk_type=ChunkType.from_string(chunk_type or "unknown"),
                language=Language.from_string(language_info or "unknown"),
                parent_header=parent_header,
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
                parent_header=chunk.get("parent_header"),
            )
        return self._provider.insert_chunk(chunk_model)

    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file."""
        from chunkhound.core.types.common import FileId

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
    
    async def delete_file_completely_async(self, file_path: str) -> bool:
        """Async version of delete_file_completely for non-blocking operation.

        Args:
            file_path: Path to file to delete completely

        Returns:
            True if deletion successful, False otherwise
        """
        if hasattr(self._provider, 'delete_file_completely_async'):
            return await self._provider.delete_file_completely_async(file_path)
        else:
            # Fallback for providers without async support
            return self._provider.delete_file_completely(file_path)

    def get_chunks_by_file_id(self, file_id: int) -> list[dict[str, Any]]:
        """Get chunks for a specific file."""
        results = self._provider.get_chunks_by_file_id(file_id, as_model=False)
        # Ensure we return Dict objects, not Chunk models
        return [result for result in results if isinstance(result, dict)]

    # =============================================================================
    # Process Coordination Methods - Legacy Support
    # =============================================================================

    def detach_database(self) -> bool:
        """Detach database for coordination."""
        with self._connection_lock:
            try:
                self._provider.disconnect()
                self.connection = None
                return True
            except Exception as e:
                logger.error(f"Failed to detach database: {e}")
                return False

    def reattach_database(self) -> bool:
        """Reattach database after coordination."""
        with self._connection_lock:
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
        with self._connection_lock:
            try:
                self._provider.disconnect()
                self.connection = None
                return True
            except Exception as e:
                logger.error(f"Failed to disconnect database: {e}")
                return False

    def reconnect(self) -> bool:
        """Reconnect database after coordination."""
        with self._connection_lock:
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

    def health_check(self) -> dict[str, Any]:
        """Perform health check and return status."""
        return self._provider.health_check()

    # =============================================================================
    # Legacy Compatibility Properties
    # =============================================================================

    # Legacy compatibility - expose db_path as attribute
    @property
    def db_path(self) -> Path | str:
        """Get database path."""
        return self._db_path

    def get_file_discovery_cache_stats(self) -> dict[str, Any]:
        """Get file discovery cache statistics."""
        return self._file_discovery_cache.get_stats()
