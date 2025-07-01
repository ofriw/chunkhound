"""DuckDB provider implementation for ChunkHound - concrete database provider using DuckDB."""

import importlib
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
from loguru import logger

# Import existing components that will be used by the provider
from chunkhound.chunker import Chunker, IncrementalChunker
from chunkhound.embeddings import EmbeddingManager
from chunkhound.file_discovery_cache import FileDiscoveryCache
from core.models import Chunk, Embedding, File
from core.types import ChunkType, Language
from providers.database.duckdb.connection_manager import DuckDBConnectionManager
from providers.database.duckdb.file_repository import DuckDBFileRepository
from providers.database.duckdb.chunk_repository import DuckDBChunkRepository
from providers.database.duckdb.embedding_repository import DuckDBEmbeddingRepository

# Avoid circular import - use lazy imports for registry functions

# Type hinting only
if TYPE_CHECKING:
    from services.embedding_service import EmbeddingService
    from services.indexing_coordinator import IndexingCoordinator
    from services.search_service import SearchService


class DuckDBProvider:
    """DuckDB implementation of DatabaseProvider protocol."""

    def __init__(self, db_path: Path | str, embedding_manager: EmbeddingManager | None = None, config: "DatabaseConfig | None" = None):
        """Initialize DuckDB provider.

        Args:
            db_path: Path to DuckDB database file or ":memory:" for in-memory database
            embedding_manager: Optional embedding manager for vector generation
            config: Database configuration for provider-specific settings
        """
        self._services_initialized = False
        self.embedding_manager = embedding_manager
        self.config = config
        self.provider_type = 'duckdb'  # Identify this as DuckDB provider
        self._in_transaction = False  # Track transaction state for atomicity

        # Initialize connection manager
        self._connection_manager = DuckDBConnectionManager(db_path, config)

        # Initialize file repository
        self._file_repository = DuckDBFileRepository(self._connection_manager)
        
        # Initialize chunk repository with provider reference for transaction awareness
        self._chunk_repository = DuckDBChunkRepository(self._connection_manager, self)
        
        # Initialize embedding repository
        self._embedding_repository = DuckDBEmbeddingRepository(self._connection_manager)
        self._embedding_repository.set_provider_instance(self)

        # Service layer components and legacy chunker instances
        self._indexing_coordinator: IndexingCoordinator | None = None
        self._search_service: SearchService | None = None
        self._embedding_service: EmbeddingService | None = None
        self._chunker: Chunker | None = None
        self._incremental_chunker: IncrementalChunker | None = None

        # File discovery cache for performance optimization
        self._file_discovery_cache = FileDiscoveryCache()

    @property
    def connection(self) -> Any | None:
        """Database connection - delegate to connection manager."""
        return self._connection_manager.connection
    
    def _get_connection(self) -> Any:
        """Get thread-safe connection for database operations.
        
        Returns thread-local cursor for async/threading safety in MCP server.
        During transactions, always uses main connection for atomicity.
        """
        # Always use main connection during transactions for atomicity
        if self._in_transaction:
            return self._connection_manager.connection
        # Use thread-safe connection in MCP mode
        if os.environ.get("CHUNKHOUND_MCP_MODE") and hasattr(self._connection_manager, 'get_thread_safe_connection'):
            return self._connection_manager.get_thread_safe_connection()
        # Fallback to main connection for backwards compatibility
        return self._connection_manager.connection

    @property
    def db_path(self) -> Path | str:
        """Database connection path or identifier - delegate to connection manager."""
        return self._connection_manager.db_path

    @property
    def is_connected(self) -> bool:
        """Check if database connection is active - delegate to connection manager."""
        return self._connection_manager.is_connected

    def _extract_file_id(self, file_record: dict[str, Any] | File) -> int | None:
        """Safely extract file ID from either dict or File model - delegate to file repository."""
        return self._file_repository._extract_file_id(file_record)

    def connect(self) -> None:
        """Establish database connection and initialize schema with WAL validation."""
        try:
            # Delegate connection, schema creation, and indexing to connection manager
            self._connection_manager.connect()

            # Initialize shared parser and chunker instances for performance
            self._initialize_shared_instances()

            logger.info("DuckDB provider initialization complete")

        except Exception as e:
            logger.error(f"DuckDB connection failed: {e}")
            raise

    def disconnect(self, skip_checkpoint: bool = False) -> None:
        """Close database connection with optional checkpointing - delegate to connection manager."""
        self._connection_manager.disconnect(skip_checkpoint)

    def health_check(self) -> dict[str, Any]:
        """Perform health check and return status information - delegate to connection manager."""
        return self._connection_manager.health_check()

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the database connection - delegate to connection manager."""
        return self._connection_manager.get_connection_info()

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database - delegate to connection manager."""
        return self._connection_manager._table_exists(table_name)

    def _get_table_name_for_dimensions(self, dims: int) -> str:
        """Get table name for given embedding dimensions - delegate to connection manager."""
        return self._connection_manager._get_table_name_for_dimensions(dims)

    def _ensure_embedding_table_exists(self, dims: int) -> str:
        """Ensure embedding table exists for given dimensions - delegate to connection manager."""
        return self._connection_manager._ensure_embedding_table_exists(dims)

    def _maybe_checkpoint(self, force: bool = False) -> None:
        """Perform checkpoint if needed - delegate to connection manager."""
        self._connection_manager._maybe_checkpoint(force)

    def _initialize_shared_instances(self):
        """Initialize service layer components and legacy compatibility objects."""
        logger.debug("Initializing service layer components")

        try:
            # Initialize chunkers for legacy compatibility
            self._chunker = Chunker()
            self._incremental_chunker = IncrementalChunker()

            # Lazy import from registry to avoid circular dependency
            registry_module = importlib.import_module('registry')
            get_registry = getattr(registry_module, 'get_registry')
            create_indexing_coordinator = getattr(registry_module, 'create_indexing_coordinator')
            create_search_service = getattr(registry_module, 'create_search_service')
            create_embedding_service = getattr(registry_module, 'create_embedding_service')

            # Get registry and register self as database provider
            registry = get_registry()
            registry.register_provider("database", lambda: self, singleton=True)

            # Initialize service layer components from registry
            if not hasattr(self, '_indexing_coordinator') or self._indexing_coordinator is None:
                self._indexing_coordinator = create_indexing_coordinator()
            if not hasattr(self, '_search_service') or self._search_service is None:
                self._search_service = create_search_service()
            if not hasattr(self, '_embedding_service') or self._embedding_service is None:
                self._embedding_service = create_embedding_service()

            logger.debug("Service layer components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize service layer components: {e}")
            # Don't raise the exception, just log it - allows test initialization to continue

    def create_schema(self) -> None:
        """Create database schema for files, chunks, and embeddings - delegate to connection manager."""
        self._connection_manager.create_schema()




    def _get_all_embedding_tables(self) -> list[str]:
        """Get list of all embedding tables (dimension-specific) - delegate to connection manager."""
        return self._connection_manager._get_all_embedding_tables()

    def create_indexes(self) -> None:
        """Create database indexes for performance optimization - delegate to connection manager."""
        self._connection_manager.create_indexes()

    def create_vector_index(self, provider: str, model: str, dims: int, metric: str = "cosine") -> None:
        """Create HNSW vector index for specific provider/model/dims combination."""
        logger.info(f"Creating HNSW index for {provider}/{model} ({dims}D, {metric})")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Get the correct table name for the dimensions
            table_name = self._get_table_name_for_dimensions(dims)

            # Ensure the table exists before creating the index
            self._ensure_embedding_table_exists(dims)

            index_name = f"hnsw_{provider}_{model}_{dims}_{metric}".replace("-", "_").replace(".", "_")

            # Create HNSW index using VSS extension on the dimension-specific table
            self._get_connection().execute(f"""
                CREATE INDEX {index_name} ON {table_name}
                USING HNSW (embedding)
                WITH (metric = '{metric}')
            """)

            logger.info(f"HNSW index {index_name} created successfully on {table_name}")

        except Exception as e:
            logger.error(f"Failed to create HNSW index: {e}")
            raise

    def drop_vector_index(self, provider: str, model: str, dims: int, metric: str = "cosine") -> str:
        """Drop HNSW vector index for specific provider/model/dims combination."""
        index_name = f"hnsw_{provider}_{model}_{dims}_{metric}".replace("-", "_").replace(".", "_")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            self._get_connection().execute(f"DROP INDEX IF EXISTS {index_name}")
            logger.info(f"HNSW index {index_name} dropped successfully")
            return index_name

        except Exception as e:
            logger.error(f"Failed to drop HNSW index {index_name}: {e}")
            raise

    def get_existing_vector_indexes(self) -> list[dict[str, Any]]:
        """Get list of existing HNSW vector indexes on all embedding tables."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Query DuckDB system tables for indexes on all embedding tables
            # Look for both legacy 'hnsw_' and standard 'idx_hnsw_' index patterns
            results = self._get_connection().execute("""
                SELECT index_name, table_name
                FROM duckdb_indexes()
                WHERE table_name LIKE 'embeddings_%'
                AND (index_name LIKE 'hnsw_%' OR index_name LIKE 'idx_hnsw_%')
            """).fetchall()

            indexes = []
            for result in results:
                index_name = result[0]
                table_name = result[1]

                # Handle different index naming patterns
                if index_name.startswith('hnsw_'):
                    # Parse custom index name: hnsw_{provider}_{model}_{dims}_{metric}
                    parts = index_name[5:].split('_')  # Remove 'hnsw_' prefix
                    if len(parts) >= 4:
                        # Reconstruct provider/model from parts (they may contain underscores)
                        metric = parts[-1]
                        dims_str = parts[-2]
                        try:
                            dims = int(dims_str)
                            # Join remaining parts as provider_model, then split on last underscore
                            provider_model = '_'.join(parts[:-2])
                            # Find last underscore to separate provider and model
                            last_underscore = provider_model.rfind('_')
                            if last_underscore > 0:
                                provider = provider_model[:last_underscore]
                                model = provider_model[last_underscore + 1:]
                            else:
                                provider = provider_model
                                model = ""

                            indexes.append({
                                'index_name': index_name,
                                'provider': provider,
                                'model': model,
                                'dims': dims,
                                'metric': metric
                            })
                        except ValueError:
                            logger.warning(f"Could not parse dims from custom index name: {index_name}")

                elif index_name.startswith('idx_hnsw_'):
                    # Parse standard index name: idx_hnsw_{dims}
                    # Extract dims from table name: embeddings_{dims}
                    try:
                        if table_name.startswith('embeddings_'):
                            dims = int(table_name[11:])  # Remove 'embeddings_' prefix
                            indexes.append({
                                'index_name': index_name,
                                'provider': 'generic',  # Standard index doesn't specify provider
                                'model': 'generic',     # Standard index doesn't specify model
                                'dims': dims,
                                'metric': 'cosine'      # Default metric for standard indexes
                            })
                    except ValueError:
                        logger.warning(f"Could not parse dims from standard index: {index_name} on {table_name}")

            return indexes

        except Exception as e:
            logger.error(f"Failed to get existing vector indexes: {e}")
            return []

    def bulk_operation_with_index_management(self, operation_func, *args, **kwargs):
        """Execute bulk operation with automatic HNSW index management and transaction safety."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        # Get existing indexes before starting
        existing_indexes = self.get_existing_vector_indexes()
        dropped_indexes = []

        try:
            # Start transaction for atomic operation
            self._get_connection().execute("BEGIN TRANSACTION")

            # Optimize settings for bulk loading
            self._get_connection().execute("SET preserve_insertion_order = false")

            # Drop existing HNSW vector indexes to improve bulk performance
            if existing_indexes:
                logger.info(f"Dropping {len(existing_indexes)} HNSW indexes for bulk operation")
                for index_info in existing_indexes:
                    try:
                        self.drop_vector_index(
                            index_info['provider'],
                            index_info['model'],
                            index_info['dims'],
                            index_info['metric']
                        )
                        dropped_indexes.append(index_info)
                    except Exception as e:
                        logger.warning(f"Could not drop index {index_info['index_name']}: {e}")

            # Execute the bulk operation
            result = operation_func(*args, **kwargs)

            # Recreate dropped indexes
            if dropped_indexes:
                logger.info(f"Recreating {len(dropped_indexes)} HNSW indexes after bulk operation")
                for index_info in dropped_indexes:
                    try:
                        self.create_vector_index(
                            index_info['provider'],
                            index_info['model'],
                            index_info['dims'],
                            index_info['metric']
                        )
                    except Exception as e:
                        logger.error(f"Failed to recreate index {index_info['index_name']}: {e}")
                        # Continue with other indexes

            # Commit transaction
            self._get_connection().execute("COMMIT")

            # Force checkpoint after bulk operations to ensure durability
            self._maybe_checkpoint(force=True)

            logger.info("Bulk operation completed successfully with index management")
            return result

        except Exception as e:
            # Rollback transaction on any error
            try:
                self._get_connection().execute("ROLLBACK")
                logger.info("Transaction rolled back due to error")
            except:
                pass

            # Attempt to recreate dropped indexes on failure
            if dropped_indexes:
                logger.info("Attempting to recreate dropped indexes after failure")
                for index_info in dropped_indexes:
                    try:
                        self.create_vector_index(
                            index_info['provider'],
                            index_info['model'],
                            index_info['dims'],
                            index_info['metric']
                        )
                    except Exception as recreate_error:
                        logger.error(f"Failed to recreate index {index_info['index_name']}: {recreate_error}")

            logger.error(f"Bulk operation failed: {e}")
            raise

    def insert_file(self, file: File) -> int:
        """Insert file record and return file ID - delegate to file repository."""
        return self._file_repository.insert_file(file)

    def get_file_by_path(self, path: str, as_model: bool = False) -> dict[str, Any] | File | None:
        """Get file record by path - delegate to file repository."""
        return self._file_repository.get_file_by_path(path, as_model)

    def get_file_by_id(self, file_id: int, as_model: bool = False) -> dict[str, Any] | File | None:
        """Get file record by ID - delegate to file repository."""
        return self._file_repository.get_file_by_id(file_id, as_model)

    def update_file(self, file_id: int, size_bytes: int | None = None, mtime: float | None = None, **kwargs) -> None:
        """Update file record with new values - delegate to file repository."""
        self._file_repository.update_file(file_id, size_bytes, mtime)

    def delete_file_completely(self, file_path: str) -> bool:
        """Delete a file and all its chunks/embeddings completely - delegate to file repository."""
        return self._file_repository.delete_file_completely(file_path)

    def insert_chunk(self, chunk: Chunk) -> int:
        """Insert chunk record and return chunk ID - delegate to chunk repository."""
        return self._chunk_repository.insert_chunk(chunk)

    def insert_chunks_batch(self, chunks: list[Chunk]) -> list[int]:
        """Insert multiple chunks in batch using optimized DuckDB bulk loading - delegate to chunk repository."""
        return self._chunk_repository.insert_chunks_batch(chunks)

    def get_chunk_by_id(self, chunk_id: int, as_model: bool = False) -> dict[str, Any] | Chunk | None:
        """Get chunk record by ID - delegate to chunk repository."""
        return self._chunk_repository.get_chunk_by_id(chunk_id, as_model)

    def get_chunks_by_file_id(self, file_id: int, as_model: bool = False) -> list[dict[str, Any] | Chunk]:
        """Get all chunks for a specific file - delegate to chunk repository."""
        return self._chunk_repository.get_chunks_by_file_id(file_id, as_model)

    def delete_file_chunks(self, file_id: int) -> None:
        """Delete all chunks for a file - delegate to chunk repository."""
        self._chunk_repository.delete_file_chunks(file_id)

    def delete_chunk(self, chunk_id: int) -> None:
        """Delete a single chunk by ID - delegate to chunk repository."""
        self._chunk_repository.delete_chunk(chunk_id)

    def update_chunk(self, chunk_id: int, **kwargs) -> None:
        """Update chunk record with new values - delegate to chunk repository."""
        self._chunk_repository.update_chunk(chunk_id, **kwargs)

    def insert_embedding(self, embedding: Embedding) -> int:
        """Insert embedding record and return embedding ID - delegate to embedding repository."""
        return self._embedding_repository.insert_embedding(embedding)

    def insert_embeddings_batch(self, embeddings_data: list[dict], batch_size: int | None = None, connection=None) -> int:
        """Insert multiple embedding vectors with HNSW index optimization - delegate to embedding repository."""
        return self._embedding_repository.insert_embeddings_batch(embeddings_data, batch_size, connection)

    def get_embedding_by_chunk_id(self, chunk_id: int, provider: str, model: str) -> Embedding | None:
        """Get embedding for specific chunk, provider, and model - delegate to embedding repository."""
        return self._embedding_repository.get_embedding_by_chunk_id(chunk_id, provider, model)

    def get_existing_embeddings(self, chunk_ids: list[int], provider: str, model: str) -> set[int]:
        """Get set of chunk IDs that already have embeddings for given provider/model - delegate to embedding repository."""
        return self._embedding_repository.get_existing_embeddings(chunk_ids, provider, model)

    def delete_embeddings_by_chunk_id(self, chunk_id: int) -> None:
        """Delete all embeddings for a specific chunk - delegate to embedding repository."""
        self._embedding_repository.delete_embeddings_by_chunk_id(chunk_id)

    def get_all_chunks_with_metadata(self) -> list[dict[str, Any]]:
        """Get all chunks with their metadata including file paths - delegate to chunk repository."""
        return self._chunk_repository.get_all_chunks_with_metadata()

    def _validate_and_normalize_path_filter(self, path_filter: str | None) -> str | None:
        """Validate and normalize path filter for security and consistency.
        
        Args:
            path_filter: User-provided path filter
            
        Returns:
            Normalized path filter safe for SQL LIKE queries, or None
            
        Raises:
            ValueError: If path contains dangerous patterns
        """
        if path_filter is None:
            return None

        # Remove leading/trailing whitespace
        normalized = path_filter.strip()

        if not normalized:
            return None

        # Security checks - prevent directory traversal
        dangerous_patterns = ['..', '~', '*', '?', '[', ']', '\0', '\n', '\r']
        for pattern in dangerous_patterns:
            if pattern in normalized:
                raise ValueError(f"Path filter contains forbidden pattern: {pattern}")

        # Normalize path separators to forward slashes
        normalized = normalized.replace('\\', '/')

        # Remove leading slashes to ensure relative paths
        normalized = normalized.lstrip('/')

        # Ensure trailing slash for directory patterns
        if normalized and not normalized.endswith('/') and '.' not in normalized.split('/')[-1]:
            normalized += '/'

        return normalized

    def search_semantic(
        self,
        query_embedding: list[float],
        provider: str,
        model: str,
        page_size: int = 10,
        offset: int = 0,
        threshold: float | None = None,
        path_filter: str | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform semantic vector search using HNSW index with multi-dimension support."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Validate and normalize path filter
            normalized_path = self._validate_and_normalize_path_filter(path_filter)

            # Detect dimensions from query embedding
            query_dims = len(query_embedding)
            table_name = self._get_table_name_for_dimensions(query_dims)

            # Check if table exists for these dimensions
            if not self._table_exists(table_name):
                logger.warning(f"No embeddings table found for {query_dims} dimensions ({table_name})")
                return [], {"offset": offset, "page_size": page_size, "has_more": False, "total": 0}

            # Build query with dimension-specific table
            query = f"""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.code,
                    c.chunk_type,
                    c.start_line,
                    c.end_line,
                    f.path as file_path,
                    f.language,
                    array_cosine_similarity(e.embedding, ?::FLOAT[{query_dims}]) as similarity
                FROM {table_name} e
                JOIN chunks c ON e.chunk_id = c.id
                JOIN files f ON c.file_id = f.id
                WHERE e.provider = ? AND e.model = ?
            """

            params = [query_embedding, provider, model]

            if threshold is not None:
                query += f" AND array_cosine_similarity(e.embedding, ?::FLOAT[{query_dims}]) >= ?"
                params.append(query_embedding)
                params.append(threshold)

            if normalized_path is not None:
                query += " AND f.path LIKE ?"
                params.append(f"%/{normalized_path}%")

            # Get total count for pagination
            # Build count query separately to avoid string replacement issues
            count_query = f"""
                SELECT COUNT(*)
                FROM {table_name} e
                JOIN chunks c ON e.chunk_id = c.id
                JOIN files f ON c.file_id = f.id
                WHERE e.provider = ? AND e.model = ?
            """

            count_params = [provider, model]

            if threshold is not None:
                count_query += f" AND array_cosine_similarity(e.embedding, ?::FLOAT[{query_dims}]) >= ?"
                count_params.extend([query_embedding, threshold])

            if normalized_path is not None:
                count_query += " AND f.path LIKE ?"
                count_params.append(f"%/{normalized_path}%")

            total_count = self._get_connection().execute(count_query, count_params).fetchone()[0]

            query += " ORDER BY similarity DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            results = self._get_connection().execute(query, params).fetchall()

            result_list = [
                {
                    "chunk_id": result[0],
                    "symbol": result[1],
                    "content": result[2],
                    "chunk_type": result[3],
                    "start_line": result[4],
                    "end_line": result[5],
                    "file_path": result[6],
                    "language": result[7],
                    "similarity": result[8]
                }
                for result in results
            ]

            pagination = {
                "offset": offset,
                "page_size": page_size,
                "has_more": offset + page_size < total_count,
                "next_offset": offset + page_size if offset + page_size < total_count else None,
                "total": total_count
            }

            return result_list, pagination

        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return [], {"offset": offset, "page_size": page_size, "has_more": False, "total": 0}

    def search_regex(self, pattern: str, page_size: int = 10, offset: int = 0, path_filter: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform regex search on code content."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Validate and normalize path filter
            normalized_path = self._validate_and_normalize_path_filter(path_filter)

            # Build base WHERE clause
            where_conditions = ["regexp_matches(c.code, ?)"]
            params = [pattern]

            if normalized_path is not None:
                where_conditions.append("f.path LIKE ?")
                params.append(f"%/{normalized_path}%")

            where_clause = " AND ".join(where_conditions)

            # Get total count for pagination
            count_query = f"""
                SELECT COUNT(*)
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE {where_clause}
            """
            total_count = self._get_connection().execute(count_query, params).fetchone()[0]

            # Get results
            results_query = f"""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.code,
                    c.chunk_type,
                    c.start_line,
                    c.end_line,
                    f.path as file_path,
                    f.language
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE {where_clause}
                ORDER BY f.path, c.start_line
                LIMIT ? OFFSET ?
            """
            results = self._get_connection().execute(results_query, params + [page_size, offset]).fetchall()



            result_list = [
                {
                    "chunk_id": result[0],
                    "name": result[1],
                    "content": result[2],
                    "chunk_type": result[3],
                    "start_line": result[4],
                    "end_line": result[5],
                    "file_path": result[6],
                    "language": result[7]
                }
                for result in results
            ]

            pagination = {
                "offset": offset,
                "page_size": page_size,
                "has_more": offset + page_size < total_count,
                "next_offset": offset + page_size if offset + page_size < total_count else None,
                "total": total_count
            }

            return result_list, pagination

        except Exception as e:
            logger.error(f"Failed to perform regex search: {e}")
            return [], {"offset": offset, "page_size": page_size, "has_more": False, "total": 0}

    def search_text(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Perform full-text search on code content."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Simple text search using LIKE operator
            search_pattern = f"%{query}%"

            results = self._get_connection().execute("""
                SELECT
                    c.id as chunk_id,
                    c.symbol,
                    c.code,
                    c.chunk_type,
                    c.start_line,
                    c.end_line,
                    f.path as file_path,
                    f.language
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE c.code LIKE ? OR c.symbol LIKE ?
                ORDER BY f.path, c.start_line
                LIMIT ?
            """, [search_pattern, search_pattern, limit]).fetchall()

            return [
                {
                    "chunk_id": result[0],
                    "name": result[1],
                    "content": result[2],
                    "chunk_type": result[3],
                    "start_line": result[4],
                    "end_line": result[5],
                    "file_path": result[6],
                    "language": result[7]
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Failed to perform text search: {e}")
            return []

    def get_stats(self) -> dict[str, int]:
        """Get database statistics (file count, chunk count, etc.)."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Get counts from each table
            file_count = self._get_connection().execute("SELECT COUNT(*) FROM files").fetchone()[0]
            chunk_count = self._get_connection().execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

            # Count embeddings across all dimension-specific tables
            embedding_count = 0
            embedding_tables = self._get_all_embedding_tables()
            for table_name in embedding_tables:
                count = self._get_connection().execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                embedding_count += count

            # Get unique providers/models across all embedding tables
            provider_results = []
            for table_name in embedding_tables:
                results = self._get_connection().execute(f"""
                    SELECT DISTINCT provider, model, COUNT(*) as count
                    FROM {table_name}
                    GROUP BY provider, model
                """).fetchall()
                provider_results.extend(results)

            providers = {}
            for result in provider_results:
                key = f"{result[0]}/{result[1]}"
                providers[key] = result[2]

            # Convert providers dict to count for interface compliance
            provider_count = len(providers)
            return {
                "files": file_count,
                "chunks": chunk_count,
                "embeddings": embedding_count,
                "providers": provider_count
            }

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"files": 0, "chunks": 0, "embeddings": 0, "providers": 0}

    def get_file_stats(self, file_id: int) -> dict[str, Any]:
        """Get statistics for a specific file - delegate to file repository."""
        return self._file_repository.get_file_stats(file_id)

    def get_provider_stats(self, provider: str, model: str) -> dict[str, Any]:
        """Get statistics for a specific embedding provider/model."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Get embedding count across all embedding tables
            embedding_count = 0
            file_ids = set()
            dims = 0
            embedding_tables = self._get_all_embedding_tables()

            for table_name in embedding_tables:
                # Count embeddings for this provider/model in this table
                count = self._get_connection().execute(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE provider = ? AND model = ?
                """, [provider, model]).fetchone()[0]
                embedding_count += count

                # Get unique file IDs for this provider/model in this table
                file_results = self._get_connection().execute(f"""
                    SELECT DISTINCT c.file_id
                    FROM {table_name} e
                    JOIN chunks c ON e.chunk_id = c.id
                    WHERE e.provider = ? AND e.model = ?
                """, [provider, model]).fetchall()
                file_ids.update(result[0] for result in file_results)

                # Get dimensions (should be consistent across all tables for same provider/model)
                if count > 0 and dims == 0:
                    dims_result = self._get_connection().execute(f"""
                        SELECT DISTINCT dims FROM {table_name}
                        WHERE provider = ? AND model = ?
                        LIMIT 1
                    """, [provider, model]).fetchone()
                    if dims_result:
                        dims = dims_result[0]

            file_count = len(file_ids)

            return {
                "provider": provider,
                "model": model,
                "embeddings": embedding_count,
                "files": file_count,
                "dimensions": dims
            }

        except Exception as e:
            logger.error(f"Failed to get provider stats for {provider}/{model}: {e}")
            return {"provider": provider, "model": model, "embeddings": 0, "files": 0, "dimensions": 0}

    def execute_query(self, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Execute a SQL query and return results."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            if params:
                results = self._get_connection().execute(query, params).fetchall()
            else:
                results = self._get_connection().execute(query).fetchall()

            # Convert to list of dictionaries
            if results:
                # Get column names
                column_names = [desc[0] for desc in self._get_connection().description]
                return [dict(zip(column_names, row)) for row in results]

            return []

        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise

    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        self._in_transaction = True
        # Use main connection for transaction atomicity
        self._connection_manager.connection.execute("BEGIN TRANSACTION")

    def commit_transaction(self, force_checkpoint: bool = False) -> None:
        """Commit the current transaction with optional checkpoint."""
        if self.connection is None:
            raise RuntimeError("No database connection")
        
        try:
            # Use main connection for transaction atomicity
            self._connection_manager.connection.execute("COMMIT")
            
            if force_checkpoint:
                try:
                    self._connection_manager.connection.execute("CHECKPOINT")
                    if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                        logger.debug("Transaction committed with checkpoint")
                except Exception as e:
                    if not os.environ.get("CHUNKHOUND_MCP_MODE"):
                        logger.warning(f"Post-commit checkpoint failed: {e}")
        finally:
            self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Use main connection for transaction atomicity
            self._connection_manager.connection.execute("ROLLBACK")
        finally:
            self._in_transaction = False

    async def process_file(self, file_path: Path, skip_embeddings: bool = False) -> dict[str, Any]:
        """Process a file end-to-end: parse, chunk, and store in database.

        Delegates to IndexingCoordinator for actual processing.
        """
        try:
            logger.info(f"Processing file: {file_path}")

            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                raise ValueError(f"File not found or not readable: {file_path}")

            # Get file metadata
            stat = file_path.stat()

            # Check if file needs to be reprocessed - delegate this logic to IndexingCoordinator
            # The code below remains for reference but is no longer used
            logger.debug(f"Delegating file processing to IndexingCoordinator: {file_path}")

            # Use IndexingCoordinator to process the file
            if not self._indexing_coordinator:
                raise RuntimeError("IndexingCoordinator not initialized")

            # Delegate to IndexingCoordinator for parsing and chunking
            # This will handle the complete file processing through the service layer
            if self._indexing_coordinator is None:
                return {"status": "error", "error": "Indexing coordinator not available"}
            return await self._indexing_coordinator.process_file(file_path, skip_embeddings=skip_embeddings)

            # Note: Embedding generation is now handled by the IndexingCoordinator
            # This code is kept for backward compatibility with legacy tests
            # Note: All embedding and chunk processing is now handled by the IndexingCoordinator
            # This provider now acts purely as a delegation layer to the service architecture

            # Delegate file processing to IndexingCoordinator and return its result directly
            return await self._indexing_coordinator.process_file(file_path, skip_embeddings=skip_embeddings)

        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return {"status": "error", "error": str(e), "chunks": 0}



    async def process_directory(
        self,
        directory: Path,
        patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """Process all supported files in a directory."""
        try:
            if patterns is None:
                patterns = ["**/*.py", "**/*.java", "**/*.cs", "**/*.ts", "**/*.js", "**/*.tsx", "**/*.jsx", "**/*.md", "**/*.markdown"]

            files_processed = 0
            total_chunks = 0
            total_embeddings = 0
            errors = []

            # Find files matching patterns
            all_files = []
            for pattern in patterns:
                files = list(directory.glob(pattern))
                all_files.extend(files)

            # Remove duplicates and filter out excluded patterns
            unique_files = list(set(all_files))
            if exclude_patterns:
                filtered_files = []
                for file_path in unique_files:
                    exclude = False
                    for exclude_pattern in exclude_patterns:
                        if file_path.match(exclude_pattern):
                            exclude = True
                            break
                    if not exclude:
                        filtered_files.append(file_path)
                unique_files = filtered_files

            logger.info(f"Processing {len(unique_files)} files in {directory}")

            # Process each file
            for file_path in unique_files:
                try:
                    # Ensure service layer is initialized
                    if not self._indexing_coordinator:
                        self._initialize_shared_instances()

                    if not self._indexing_coordinator:
                        errors.append(f"{file_path}: IndexingCoordinator not available")
                        continue

                    # Delegate to IndexingCoordinator for file processing
                    result = await self._indexing_coordinator.process_file(file_path, skip_embeddings=False)

                    if result["status"] == "success":
                        files_processed += 1
                        total_chunks += result.get("chunks", 0)
                        total_embeddings += result.get("embeddings", 0)
                    elif result["status"] == "error":
                        errors.append(f"{file_path}: {result.get('error', 'Unknown error')}")
                    # Skip files with status "up_to_date", "skipped", etc.

                except Exception as e:
                    error_msg = f"{file_path}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error processing {file_path}: {e}")

            result = {
                "status": "success",
                "files_processed": files_processed,
                "total_files": len(unique_files),
                "total_chunks": total_chunks,
                "total_embeddings": total_embeddings
            }

            if errors:
                result["errors"] = errors
                result["error_count"] = len(errors)

            logger.info(f"Directory processing complete: {files_processed}/{len(unique_files)} files, "
                       f"{total_chunks} chunks, {total_embeddings} embeddings")

            return result

        except Exception as e:
            logger.error(f"Failed to process directory {directory}: {e}")
            return {"status": "error", "error": str(e), "files_processed": 0}

    def optimize_tables(self) -> None:
        """Optimize tables by compacting fragments and rebuilding indexes (provider-specific)."""
        # DuckDB automatically manages table optimization through its WAL and MVCC system
        # No manual optimization needed for DuckDB
        pass
        
