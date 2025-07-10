"""Indexing coordinator service for ChunkHound - orchestrates indexing workflows."""

import asyncio
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from loguru import logger
from tqdm import tqdm

from chunkhound.core.models import File
from chunkhound.core.types.common import FileId, FilePath, Language
from chunkhound.interfaces.database_provider import DatabaseProvider
from chunkhound.interfaces.embedding_provider import EmbeddingProvider
from chunkhound.interfaces.language_parser import LanguageParser, ParseResult

from .base_service import BaseService
from .chunk_cache_service import ChunkCacheService


class IndexingCoordinator(BaseService):
    """Coordinates file indexing workflows with parsing, chunking, and embeddings."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider | None = None,
        language_parsers: dict[Language, LanguageParser] | None = None,
    ):
        """Initialize indexing coordinator.

        Args:
            database_provider: Database provider for persistence
            embedding_provider: Optional embedding provider for vector generation
            language_parsers: Optional mapping of language to parser implementations
        """
        super().__init__(database_provider)
        self._embedding_provider = embedding_provider
        self._language_parsers = language_parsers or {}

        # Performance optimization: shared instances
        self._parser_cache: dict[Language, LanguageParser] = {}

        # Chunk cache service for content-based comparison
        self._chunk_cache = ChunkCacheService()

        # File-level locking to prevent concurrent processing of the same file
        # Using a regular dict to store lock references - locks will be created lazily
        # within the event loop context to ensure proper event loop binding
        self._file_locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = None  # Will be initialized when first needed

    def add_language_parser(self, language: Language, parser: LanguageParser) -> None:
        """Add or update a language parser.

        Args:
            language: Programming language identifier
            parser: Parser implementation for the language
        """
        self._language_parsers[language] = parser
        # Clear cache for this language
        if language in self._parser_cache:
            del self._parser_cache[language]

    def get_parser_for_language(self, language: Language) -> LanguageParser | None:
        """Get parser for specified language with caching.

        Args:
            language: Programming language identifier

        Returns:
            Parser instance or None if not supported
        """
        if language not in self._parser_cache:
            if language in self._language_parsers:
                parser = self._language_parsers[language]
                # Parser setup() already called during registration - no need to call again
                self._parser_cache[language] = parser
            else:
                return None

        return self._parser_cache[language]

    def detect_file_language(self, file_path: Path) -> Language | None:
        """Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            Language enum value or None if unsupported
        """
        language = Language.from_file_extension(file_path)
        return language if language != Language.UNKNOWN else None

    async def _get_file_lock(self, file_path: Path) -> asyncio.Lock:
        """Get or create a lock for the given file path.

        Creates locks lazily within the event loop context to ensure proper binding.
        Uses a lock to protect the locks dictionary itself from concurrent access.

        Args:
            file_path: Path to the file

        Returns:
            AsyncIO lock for the file
        """
        # Initialize the locks lock if needed (first time, in event loop context)
        if self._locks_lock is None:
            self._locks_lock = asyncio.Lock()

        file_key = str(file_path.absolute())

        # Use the locks lock to ensure thread-safe access to the locks dictionary
        async with self._locks_lock:
            if file_key not in self._file_locks:
                # Create the lock within the event loop context
                self._file_locks[file_key] = asyncio.Lock()
            return self._file_locks[file_key]

    def _cleanup_file_lock(self, file_path: Path) -> None:
        """Remove lock for a file that no longer exists.

        Args:
            file_path: Path to the file
        """
        file_key = str(file_path.absolute())
        if file_key in self._file_locks:
            del self._file_locks[file_key]
            logger.debug(f"Cleaned up lock for deleted file: {file_key}")

    async def process_file(
        self, file_path: Path, skip_embeddings: bool = False
    ) -> dict[str, Any]:
        """Process a single file through the complete indexing pipeline.

        Args:
            file_path: Path to the file to process
            skip_embeddings: If True, skip embedding generation for batch processing

        Returns:
            Dictionary with processing results including status, chunks, and embeddings
        """

        # Acquire file-level lock to prevent concurrent processing
        file_lock = await self._get_file_lock(file_path)
        async with file_lock:
            return await self._process_file_locked(file_path, skip_embeddings)

    async def _process_file_locked(
        self, file_path: Path, skip_embeddings: bool = False
    ) -> dict[str, Any]:
        """Process file with lock held - internal implementation.

        Args:
            file_path: Path to the file to process
            skip_embeddings: If True, skip embedding generation for batch processing

        Returns:
            Dictionary with processing results
        """
        try:
            # Validate file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return {
                    "status": "error",
                    "error": f"File not found: {file_path}",
                    "chunks": 0,
                }

            # Detect language
            language = self.detect_file_language(file_path)
            if not language:
                return {"status": "skipped", "reason": "unsupported_type", "chunks": 0}

            # Get parser for language
            parser = self.get_parser_for_language(language)
            if not parser:
                return {
                    "status": "error",
                    "error": f"No parser available for {language}",
                    "chunks": 0,
                }

            # Get file stats for storage/update operations
            file_stat = file_path.stat()

            logger.debug(f"Processing file: {file_path}")
            logger.debug(
                f"File stat: mtime={file_stat.st_mtime}, size={file_stat.st_size}"
            )

            # Note: Removed timestamp checking logic - if process_file()
            # was called, the file needs processing. File watcher handles change detection.

            # Parse file content - can return ParseResult or List[Dict[str, Any]]
            parsed_data = parser.parse_file(file_path)
            if not parsed_data:
                return {"status": "no_content", "chunks": 0}

            # Extract chunks from ParseResult object or direct list
            raw_chunks: list[dict[str, Any]]
            if isinstance(parsed_data, ParseResult):
                # New parser providers return ParseResult object
                raw_chunks = parsed_data.chunks
            elif isinstance(parsed_data, list):
                # Legacy parsers return chunks directly
                raw_chunks = parsed_data
            else:
                # Fallback for unexpected types
                raw_chunks = []

            # Filter empty chunks early to reduce storage warnings
            chunks = self._filter_valid_chunks(raw_chunks)

            if not chunks:
                return {"status": "no_chunks", "chunks": 0}

            # Always process files - let chunk-level comparison handle change detection
            # Store or update file record
            file_id = self._store_file_record(file_path, file_stat, language)
            if file_id is None:
                return {
                    "status": "error",
                    "chunks": 0,
                    "error": "Failed to store file record",
                }

            # Check for existing file to determine if this is an update or new file
            existing_file = self._db.get_file_by_path(str(file_path))

            # Smart chunk update for existing files to preserve embeddings
            if existing_file:
                # CRITICAL: Always clean up old chunks for existing files to prevent content deletion bug
                # This ensures that stale chunks don't persist in the database when files are modified

                # Convert new chunks to models for comparison
                new_chunk_models = self._convert_to_chunk_models(
                    file_id, chunks, language
                )

                # Wrap entire update in a transaction for atomicity
                try:
                    self._db.begin_transaction()

                    # CRITICAL FIX: Get existing chunks INSIDE transaction to prevent race condition
                    # This ensures we see the latest state and prevents duplicate insertions
                    existing_chunks = self._db.get_chunks_by_file_id(
                        file_id, as_model=True
                    )

                    # ALWAYS process existing files with transaction safety, regardless of existing_chunks
                    # This fixes the content deletion bug where old chunks persist when existing_chunks is empty
                    logger.debug(
                        f"Processing existing file with {len(existing_chunks)} existing chunks"
                    )

                    if existing_chunks:
                        # Perform smart diff to identify what changed
                        chunk_diff = self._chunk_cache.diff_chunks(
                            new_chunk_models, existing_chunks
                        )

                        logger.debug(
                            f"Smart diff results for file_id {file_id}: "
                            f"unchanged={len(chunk_diff.unchanged)}, "
                            f"added={len(chunk_diff.added)}, "
                            f"modified={len(chunk_diff.modified)}, "
                            f"deleted={len(chunk_diff.deleted)}"
                        )

                        # Delete all chunks that were modified or removed
                        chunks_to_delete = chunk_diff.deleted + chunk_diff.modified
                        if chunks_to_delete:
                            chunk_ids_to_delete = [
                                chunk.id
                                for chunk in chunks_to_delete
                                if chunk.id is not None
                            ]
                            if chunk_ids_to_delete:
                                logger.debug(
                                    f"Deleting {len(chunk_ids_to_delete)} chunks with IDs: {chunk_ids_to_delete}"
                                )
                                for chunk_id in chunk_ids_to_delete:
                                    self._db.delete_chunk(chunk_id)
                                logger.debug(
                                    f"Successfully deleted {len(chunk_ids_to_delete)} modified/removed chunks"
                                )

                        # Insert only new and modified chunks
                        chunks_to_store = []
                        chunks_to_store.extend(
                            [chunk.to_dict() for chunk in chunk_diff.added]
                        )
                        chunks_to_store.extend(
                            [chunk.to_dict() for chunk in chunk_diff.modified]
                        )

                        if chunks_to_store:
                            logger.debug(
                                f"Storing {len(chunks_to_store)} new/modified chunks"
                            )
                            chunk_ids_new = self._store_chunks(
                                file_id, chunks_to_store, language
                            )
                        else:
                            chunk_ids_new = []

                        # Combine IDs: unchanged chunks keep their IDs (and embeddings!)
                        unchanged_ids = [
                            chunk.id
                            for chunk in chunk_diff.unchanged
                            if chunk.id is not None
                        ]
                        chunk_ids = unchanged_ids + chunk_ids_new

                        # Generate embeddings only for new/modified chunks
                        chunks_needing_embeddings = chunks_to_store
                        chunk_ids_needing_embeddings = chunk_ids_new

                        logger.debug(
                            f"Smart chunk update complete: {len(chunk_diff.unchanged)} preserved, "
                            f"{len(chunk_diff.added)} added, {len(chunk_diff.modified)} modified, "
                            f"{len(chunk_diff.deleted)} deleted"
                        )
                    else:
                        # No existing chunks found - this could be due to race conditions or inconsistencies
                        # CRITICAL FIX: Always clean up ALL chunks for this file_id to prevent stale data
                        logger.debug(
                            f"No existing chunks found for file_id {file_id}, cleaning up any stale chunks"
                        )

                        # Force cleanup of any chunks that might exist for this file
                        self._db.delete_file_chunks(file_id)

                        # Store all new chunks
                        chunks_dict = [chunk.to_dict() for chunk in new_chunk_models]
                        chunk_ids = self._store_chunks(file_id, chunks_dict, language)

                        # All chunks need embeddings
                        chunks_needing_embeddings = chunks_dict
                        chunk_ids_needing_embeddings = chunk_ids

                        logger.debug(
                            f"Stored {len(chunk_ids)} new chunks after cleanup"
                        )

                    # Commit the transaction - this makes all changes atomic
                    self._db.commit_transaction()
                    logger.debug("Transaction committed successfully")

                except Exception as e:
                    # Rollback on any error to prevent partial updates
                    logger.error(f"Chunk update failed, rolling back: {e}")
                    try:
                        self._db.rollback_transaction()
                    except Exception as rollback_error:
                        logger.error(f"Rollback failed: {rollback_error}")
                    raise
            else:
                # New file, wrap in transaction for consistency
                chunk_models = self._convert_to_chunk_models(file_id, chunks, language)
                chunks_dict = [chunk.to_dict() for chunk in chunk_models]

                try:
                    self._db.begin_transaction()

                    # Store chunks inside transaction
                    chunk_ids = self._store_chunks(file_id, chunks_dict, language)

                    # Commit transaction
                    self._db.commit_transaction()
                    logger.debug("New file transaction committed successfully")

                except Exception as e:
                    # Rollback on any error
                    logger.error(f"New file chunk storage failed, rolling back: {e}")
                    try:
                        self._db.rollback_transaction()
                    except Exception as rollback_error:
                        logger.error(f"Rollback failed: {rollback_error}")
                    raise

                # All chunks need embeddings for new files
                chunks_needing_embeddings = chunks_dict
                chunk_ids_needing_embeddings = chunk_ids

            # Generate embeddings with correctly aligned data
            embeddings_generated = 0
            if not skip_embeddings and chunk_ids_needing_embeddings:
                if self._embedding_provider:
                    embeddings_generated = await self._generate_embeddings(
                        chunk_ids_needing_embeddings, chunks_needing_embeddings
                    )
                else:
                    logger.warning(
                        f"Embedding provider is None - skipping embedding generation for {len(chunk_ids_needing_embeddings)} chunks"
                    )
            elif skip_embeddings:
                logger.debug("Skipping embedding generation (skip_embeddings=True)")
            elif not chunk_ids_needing_embeddings:
                logger.debug("No chunks need embeddings")

            result = {
                "status": "success",
                "file_id": file_id,
                "chunks": len(chunks),
                "chunk_ids": chunk_ids,
                "embeddings": embeddings_generated,
            }

            # Include chunk data for batch processing
            if skip_embeddings:
                result["chunk_data"] = chunks

            return result

        except Exception as e:
            import traceback

            logger.error(f"Failed to process file {file_path}: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return {"status": "error", "error": str(e), "chunks": 0}

    async def _process_file_modification_safe(
        self,
        file_id: int,
        file_path: Path,
        file_stat,
        chunks: list[dict[str, Any]],
        language: Language,
        skip_embeddings: bool,
    ) -> tuple[list[int], int]:
        """Process file modification with transaction safety to prevent data loss.

        This method ensures that old content is preserved if new content processing fails.
        Uses database transactions and backup tables for rollback capability.

        Args:
            file_id: Existing file ID in database
            file_path: Path to the file being processed
            file_stat: File stat object with mtime and size
            chunks: New chunks to store
            language: File language type
            skip_embeddings: Whether to skip embedding generation

        Returns:
            Tuple of (chunk_ids, embeddings_generated)

        Raises:
            Exception: If transaction-safe processing fails and rollback is needed
        """
        import time

        logger.debug(f"Transaction-safe processing - Starting for file_id: {file_id}")

        # Create unique backup table names using timestamp
        timestamp = int(time.time() * 1000000)  # microseconds for uniqueness
        chunks_backup_table = f"chunks_backup_{timestamp}"
        embeddings_backup_table = f"embeddings_1536_backup_{timestamp}"

        connection = self._db.connection
        if connection is None:
            raise RuntimeError("Database connection not available")

        try:
            # Start transaction
            connection.execute("BEGIN TRANSACTION")
            logger.debug("Transaction-safe processing - Transaction started")

            # Get count of existing chunks for reporting
            existing_chunks_count = connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE file_id = ?", [file_id]
            ).fetchone()[0]
            logger.debug(
                f"Transaction-safe processing - Found {existing_chunks_count} existing chunks"
            )

            # Create backup table for chunks
            connection.execute(
                f"""
                CREATE TABLE {chunks_backup_table} AS
                SELECT * FROM chunks WHERE file_id = ?
            """,
                [file_id],
            )
            logger.debug(
                f"Transaction-safe processing - Created backup table: {chunks_backup_table}"
            )

            # Create backup table for embeddings
            connection.execute(
                f"""
                CREATE TABLE {embeddings_backup_table} AS
                SELECT e.* FROM embeddings_1536 e
                JOIN chunks c ON e.chunk_id = c.id
                WHERE c.file_id = ?
            """,
                [file_id],
            )
            logger.debug(
                f"Transaction-safe processing - Created embedding backup: {embeddings_backup_table}"
            )

            # Update file metadata first
            self._db.update_file(
                file_id, size_bytes=file_stat.st_size, mtime=file_stat.st_mtime
            )

            # Remove old content (but backup preserved in transaction)
            self._db.delete_file_chunks(file_id)
            logger.debug("Transaction-safe processing - Removed old content")

            # Store new chunks
            chunk_ids = self._store_chunks(file_id, chunks, language)
            if not chunk_ids:
                raise Exception("Failed to store new chunks")
            logger.debug(
                f"Transaction-safe processing - Stored {len(chunk_ids)} new chunks"
            )

            # Generate embeddings if requested
            embeddings_generated = 0
            if not skip_embeddings and self._embedding_provider and chunk_ids:
                embeddings_generated = await self._generate_embeddings(
                    chunk_ids, chunks, connection
                )
                logger.debug(
                    f"Transaction-safe processing - Generated {embeddings_generated} embeddings"
                )

            # Commit transaction
            connection.execute("COMMIT")
            logger.debug(
                "Transaction-safe processing - Transaction committed successfully"
            )

            # Cleanup backup tables
            try:
                connection.execute(f"DROP TABLE {chunks_backup_table}")
                connection.execute(f"DROP TABLE {embeddings_backup_table}")
                logger.debug("Transaction-safe processing - Backup tables cleaned up")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup backup tables: {cleanup_error}")

            return chunk_ids, embeddings_generated

        except Exception as e:
            logger.error(f"Transaction-safe processing failed: {e}")

            try:
                # Rollback transaction
                connection.execute("ROLLBACK")
                logger.debug("Transaction-safe processing - Transaction rolled back")

                # Restore from backup tables if they exist
                try:
                    # Check if backup tables still exist
                    backup_exists = (
                        connection.execute(f"""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_name='{chunks_backup_table}'
                    """).fetchone()[0]
                        > 0
                    )

                    if backup_exists:
                        # Restore chunks from backup
                        connection.execute(f"""
                            INSERT INTO chunks SELECT * FROM {chunks_backup_table}
                        """)

                        # Restore embeddings from backup
                        connection.execute(f"""
                            INSERT INTO embeddings_1536 SELECT * FROM {embeddings_backup_table}
                        """)

                        logger.info(
                            "Transaction-safe processing - Original content restored from backup"
                        )

                        # Cleanup backup tables
                        connection.execute(f"DROP TABLE {chunks_backup_table}")
                        connection.execute(f"DROP TABLE {embeddings_backup_table}")

                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")

            # Re-raise the original exception
            raise e

    async def process_directory(
        self,
        directory: Path,
        patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Process all supported files in a directory with batch optimization and consistency checks.

        Args:
            directory: Directory path to process
            patterns: Optional file patterns to include
            exclude_patterns: Optional file patterns to exclude

        Returns:
            Dictionary with processing statistics
        """
        try:
            # Phase 1: Discovery - Discover files in directory
            files = self._discover_files(directory, patterns, exclude_patterns)

            if not files:
                return {"status": "no_files", "files_processed": 0, "total_chunks": 0}

            # Phase 2: Reconciliation - Ensure database consistency by removing orphaned files
            cleaned_files = self._cleanup_orphaned_files(
                directory, files, exclude_patterns
            )

            logger.debug(
                f"Directory consistency: {len(files)} files discovered, {cleaned_files} orphaned files cleaned"
            )

            # Phase 3: Update - Process files with enhanced cache logic
            total_files = 0
            total_chunks = 0

            # Create progress bar for file processing
            with tqdm(total=len(files), desc="Processing files", unit="file") as pbar:
                for file_path in files:
                    result = await self.process_file(file_path, skip_embeddings=True)

                    if result["status"] in ["success", "up_to_date"]:
                        total_files += 1
                        total_chunks += result["chunks"]
                        pbar.set_postfix_str(f"{total_chunks} chunks")
                    elif result["status"] in ["skipped", "no_content", "no_chunks"]:
                        # Still update progress for skipped files
                        pass
                    else:
                        # Log errors but continue processing
                        logger.warning(
                            f"Failed to process {file_path}: {result.get('error', 'unknown error')}"
                        )

                    pbar.update(1)

            # Note: Embedding generation is handled separately via generate_missing_embeddings()
            # to provide a unified progress experience

            # Optimize tables after bulk operations (provider-specific)
            if total_chunks > 0 and hasattr(self._db, "optimize_tables"):
                logger.debug("Optimizing database tables after bulk operations...")
                self._db.optimize_tables()

            return {
                "status": "success",
                "files_processed": total_files,
                "total_chunks": total_chunks,
            }

        except Exception as e:
            logger.error(f"Failed to process directory {directory}: {e}")
            return {"status": "error", "error": str(e)}

    def _extract_file_id(self, file_record: dict[str, Any] | File) -> int | None:
        """Safely extract file ID from either dict or File model."""
        if isinstance(file_record, File):
            return file_record.id
        elif isinstance(file_record, dict) and "id" in file_record:
            return file_record["id"]
        else:
            return None

    def _store_file_record(
        self, file_path: Path, file_stat: Any, language: Language
    ) -> int:
        """Store or update file record in database."""
        # Check if file already exists
        existing_file = self._db.get_file_by_path(str(file_path))

        if existing_file:
            # Update existing file with new metadata
            if isinstance(existing_file, dict) and "id" in existing_file:
                file_id = existing_file["id"]
                self._db.update_file(
                    file_id, size_bytes=file_stat.st_size, mtime=file_stat.st_mtime
                )
                return file_id

        # Create new File model instance
        file_model = File(
            path=FilePath(str(file_path)),
            size_bytes=file_stat.st_size,
            mtime=file_stat.st_mtime,
            language=language,
        )
        return self._db.insert_file(file_model)

    def _filter_valid_chunks(
        self, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter out chunks with empty content early in the process."""
        valid_chunks = []
        filtered_count = 0

        for chunk in chunks:
            code_content = chunk.get("code", "")
            if code_content and code_content.strip():
                valid_chunks.append(chunk)
            else:
                filtered_count += 1

        # Log summary instead of individual warnings to reduce noise
        if filtered_count > 0:
            logger.debug(f"Filtered {filtered_count} empty chunks during parsing")

        return valid_chunks

    def _store_chunks(
        self, file_id: int, chunks: list[dict[str, Any]], language: Language
    ) -> list[int]:
        """Store chunks in database and return chunk IDs."""
        if not chunks:
            return []

        # Create Chunk model instances for batch insertion
        from chunkhound.core.models import Chunk
        from chunkhound.core.types.common import ChunkType

        chunk_models = []
        for chunk in chunks:
            # Convert chunk_type string to enum
            chunk_type_str = chunk.get("chunk_type", "function")
            try:
                chunk_type_enum = ChunkType(chunk_type_str)
            except ValueError:
                chunk_type_enum = ChunkType.FUNCTION  # default fallback

            chunk_model = Chunk(
                file_id=FileId(file_id),
                symbol=chunk.get("symbol", ""),
                start_line=chunk.get("start_line", 0),
                end_line=chunk.get("end_line", 0),
                code=chunk.get("code", ""),
                chunk_type=chunk_type_enum,
                language=language,  # Use the file's detected language
                parent_header=chunk.get("parent_header"),
            )
            chunk_models.append(chunk_model)

        # Use batch insertion for optimal performance
        chunk_ids = self._db.insert_chunks_batch(chunk_models)

        # Log batch operation
        logger.debug(f"Batch inserted {len(chunk_ids)} chunks for file_id {file_id}")

        return chunk_ids

    def _convert_to_chunk_models(
        self, file_id: int, chunks: list[dict[str, Any]], language: Language
    ) -> list["Chunk"]:
        """Convert dict chunks to Chunk models without storing in database."""
        from chunkhound.core.models import Chunk
        from chunkhound.core.types.common import ChunkType

        chunk_models = []
        for chunk in chunks:
            # Convert chunk_type string to enum
            chunk_type_str = chunk.get("chunk_type", "function")
            try:
                chunk_type_enum = ChunkType(chunk_type_str)
            except ValueError:
                chunk_type_enum = ChunkType.FUNCTION  # default fallback

            chunk_model = Chunk(
                file_id=FileId(file_id),
                symbol=chunk.get("symbol", ""),
                start_line=chunk.get("start_line", 0),
                end_line=chunk.get("end_line", 0),
                code=chunk.get("code", ""),
                chunk_type=chunk_type_enum,
                language=language,
                parent_header=chunk.get("parent_header"),
            )
            chunk_models.append(chunk_model)

        return chunk_models

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with file, chunk, and embedding counts
        """
        return self._db.get_stats()

    async def remove_file(self, file_path: str) -> int:
        """Remove a file and all its chunks from the database.

        Args:
            file_path: Path to the file to remove

        Returns:
            Number of chunks removed
        """
        try:
            # Get file record to get chunk count before deletion
            file_record = self._db.get_file_by_path(file_path)
            if not file_record:
                return 0

            # Get file ID
            file_id = self._extract_file_id(file_record)
            if file_id is None:
                return 0

            # Count chunks before deletion
            chunks = self._db.get_chunks_by_file_id(file_id)
            chunk_count = len(chunks) if chunks else 0

            # Delete the file completely (this will also delete chunks and embeddings)
            success = self._db.delete_file_completely(file_path)

            # Clean up the file lock since the file no longer exists
            if success:
                self._cleanup_file_lock(Path(file_path))

            return chunk_count if success else 0

        except Exception as e:
            logger.error(f"Failed to remove file {file_path}: {e}")
            return 0

    async def generate_missing_embeddings(
        self, exclude_patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """Generate embeddings for chunks that don't have them.

        Args:
            exclude_patterns: Optional file patterns to exclude from embedding generation

        Returns:
            Dictionary with generation results
        """
        if not self._embedding_provider:
            return {
                "status": "error",
                "error": "No embedding provider configured",
                "generated": 0,
            }

        try:
            # Use EmbeddingService for embedding generation
            from .embedding_service import EmbeddingService

            # Get optimization frequency from config or use default
            optimization_batch_frequency = 1000
            if hasattr(self._db, "_config") and self._db._config:
                optimization_batch_frequency = getattr(
                    self._db._config.embedding, "optimization_batch_frequency", 1000
                )
            
            embedding_service = EmbeddingService(
                database_provider=self._db, 
                embedding_provider=self._embedding_provider,
                optimization_batch_frequency=optimization_batch_frequency
            )

            return await embedding_service.generate_missing_embeddings(
                exclude_patterns=exclude_patterns
            )

        except Exception as e:
            logger.error(f"Failed to generate missing embeddings: {e}")
            return {"status": "error", "error": str(e), "generated": 0}

    async def _generate_embeddings(
        self, chunk_ids: list[int], chunks: list[dict[str, Any]], connection=None
    ) -> int:
        """Generate embeddings for chunks."""
        if not self._embedding_provider:
            return 0

        try:
            # Filter out chunks with empty text content before embedding
            valid_chunk_data = []
            empty_count = 0
            for chunk_id, chunk in zip(chunk_ids, chunks):
                text = chunk.get("code", "").strip()
                if text:  # Only include chunks with actual content
                    valid_chunk_data.append((chunk_id, chunk, text))
                else:
                    empty_count += 1

            # Log metrics for empty chunks
            if empty_count > 0:
                logger.debug(
                    f"Filtered {empty_count} empty text chunks before embedding generation"
                )

            if not valid_chunk_data:
                logger.debug(
                    "No valid chunks with text content for embedding generation"
                )
                return 0

            # Extract data for embedding generation
            valid_chunk_ids = [chunk_id for chunk_id, _, _ in valid_chunk_data]
            [chunk for _, chunk, _ in valid_chunk_data]
            texts = [text for _, _, text in valid_chunk_data]

            # Generate embeddings (progress tracking handled by missing embeddings phase)
            embedding_results = await self._embedding_provider.embed(texts)

            # Store embeddings in database
            embeddings_data = []
            for chunk_id, vector in zip(valid_chunk_ids, embedding_results):
                embeddings_data.append(
                    {
                        "chunk_id": chunk_id,
                        "provider": self._embedding_provider.name,
                        "model": self._embedding_provider.model,
                        "dims": len(vector),
                        "embedding": vector,
                    }
                )

            # Database storage - use provided connection for transaction context
            result = self._db.insert_embeddings_batch(
                embeddings_data, connection=connection
            )

            return result

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return 0

    async def _generate_embeddings_batch(
        self, file_chunks: list[tuple[int, dict[str, Any]]]
    ) -> int:
        """Generate embeddings for chunks in optimized batches."""
        if not self._embedding_provider or not file_chunks:
            return 0

        # Extract chunk IDs and text content
        chunk_ids = [chunk_id for chunk_id, _ in file_chunks]
        chunks = [chunk_data for _, chunk_data in file_chunks]

        return await self._generate_embeddings(chunk_ids, chunks)

    def _discover_files(
        self,
        directory: Path,
        patterns: list[str] | None,
        exclude_patterns: list[str] | None,
    ) -> list[Path]:
        """Discover files in directory matching patterns with efficient exclude filtering.

        Args:
            directory: Directory to search
            patterns: File patterns to include (REQUIRED - must be provided by configuration layer)
            exclude_patterns: File patterns to exclude (optional - will load from config if None)

        Raises:
            ValueError: If patterns is None/empty (configuration layer error)
        """

        # Validate inputs - fail fast on configuration errors
        if not patterns:
            raise ValueError(
                "patterns parameter is required for directory discovery. "
                "Configuration layer must provide file patterns."
            )

        # Default exclude patterns from unified config with .gitignore support
        if not exclude_patterns:
            from chunkhound.core.config.unified_config import ChunkHoundConfig

            config = ChunkHoundConfig.load_hierarchical(project_dir=directory)
            exclude_patterns = config.indexing.get_effective_exclude_patterns(directory)

        # Use custom directory walker that respects exclude patterns during traversal
        discovered_files = self._walk_directory_with_excludes(
            directory, patterns, exclude_patterns
        )

        return sorted(discovered_files)

    def _walk_directory_with_excludes(
        self, directory: Path, patterns: list[str], exclude_patterns: list[str]
    ) -> list[Path]:
        """Custom directory walker that skips excluded directories during traversal.

        Args:
            directory: Root directory to walk
            patterns: File patterns to include
            exclude_patterns: Patterns to exclude (applied to both files and directories)

        Returns:
            List of file paths that match include patterns and don't match exclude patterns
        """
        files = []

        def should_exclude_path(path: Path, base_dir: Path) -> bool:
            """Check if a path should be excluded based on exclude patterns."""
            try:
                rel_path = path.relative_to(base_dir)
            except ValueError:
                # Path is not under base directory, use absolute path
                rel_path = path

            for exclude_pattern in exclude_patterns:
                # Handle ** patterns that fnmatch doesn't support properly
                if exclude_pattern.startswith("**/") and exclude_pattern.endswith(
                    "/**"
                ):
                    # Extract the directory name from pattern like **/.venv/**
                    target_dir = exclude_pattern[3:-3]  # Remove **/ and /**
                    if target_dir in rel_path.parts or target_dir in path.parts:
                        return True
                elif exclude_pattern.startswith("**/"):
                    # Pattern like **/*.db - check if any part matches the suffix
                    suffix = exclude_pattern[3:]  # Remove **/
                    if (
                        fnmatch(str(rel_path), suffix)
                        or fnmatch(str(path), suffix)
                        or fnmatch(rel_path.name, suffix)
                        or fnmatch(path.name, suffix)
                    ):
                        return True
                else:
                    # Regular fnmatch for non-** patterns
                    if fnmatch(str(rel_path), exclude_pattern) or fnmatch(
                        str(path), exclude_pattern
                    ):
                        return True
            return False

        def should_include_file(file_path: Path) -> bool:
            """Check if a file matches any of the include patterns."""
            try:
                rel_path = file_path.relative_to(directory)
            except ValueError:
                # File is not under base directory, use absolute path
                rel_path = file_path

            for pattern in patterns:
                rel_path_str = str(rel_path)
                filename = file_path.name

                # Handle **/ prefix patterns (common from CLI conversion)
                if pattern.startswith("**/"):
                    simple_pattern = pattern[
                        3:
                    ]  # Remove **/ prefix (e.g., *.md from **/*.md)

                    # Match against:
                    # 1. Full relative path for nested files (e.g., "docs/guide.md" matches "**/*.md")
                    # 2. Simple pattern for root-level files (e.g., "README.md" matches "*.md")
                    # 3. Filename only for simple patterns (e.g., "guide.md" matches "*.md")
                    if (
                        fnmatch(rel_path_str, pattern)
                        or fnmatch(rel_path_str, simple_pattern)
                        or fnmatch(filename, simple_pattern)
                    ):
                        return True
                else:
                    # Regular pattern - check both relative path and filename
                    if fnmatch(rel_path_str, pattern) or fnmatch(filename, pattern):
                        return True
            return False

        # Walk directory tree manually to control traversal
        def walk_recursive(current_dir: Path) -> None:
            """Recursively walk directory, skipping excluded paths."""
            try:
                # Get directory contents
                for entry in current_dir.iterdir():
                    # Skip if path should be excluded
                    if should_exclude_path(entry, directory):
                        continue

                    if entry.is_file():
                        # Check if file matches include patterns
                        if should_include_file(entry):
                            files.append(entry)
                    elif entry.is_dir():
                        # Recursively walk subdirectory (already checked it's not excluded)
                        walk_recursive(entry)

            except (PermissionError, OSError) as e:
                # Log warning but continue with other directories
                logger.debug(
                    f"Skipping directory due to access error: {current_dir} - {e}"
                )

        # Start walking from the root directory
        walk_recursive(directory)

        return files

    def _cleanup_orphaned_files(
        self,
        directory: Path,
        current_files: list[Path],
        exclude_patterns: list[str] | None = None,
    ) -> int:
        """Remove database entries for files that no longer exist in the directory.

        Args:
            directory: Directory being processed
            current_files: List of files currently in the directory
            exclude_patterns: Optional list of exclude patterns to check against

        Returns:
            Number of orphaned files cleaned up
        """
        try:
            # Create set of absolute paths for fast lookup
            current_file_paths = {
                str(file_path.absolute()) for file_path in current_files
            }

            # Get all files in database that are under this directory
            directory_str = str(directory.absolute())
            query = """
                SELECT id, path
                FROM files
                WHERE path LIKE ? || '%'
            """
            db_files = self._db.execute_query(query, [directory_str])

            # Find orphaned files (in DB but not on disk or excluded by patterns)
            orphaned_files = []
            if not exclude_patterns:
                from chunkhound.core.config.unified_config import ChunkHoundConfig

                patterns_to_check = ChunkHoundConfig.get_default_exclude_patterns()
            else:
                patterns_to_check = exclude_patterns

            for db_file in db_files:
                file_path = db_file["path"]

                # Check if file should be excluded based on current patterns
                should_exclude = False

                # Convert to Path for relative path calculation
                file_path_obj = Path(file_path)
                try:
                    rel_path = file_path_obj.relative_to(directory)
                except ValueError:
                    # File is not under the directory, use absolute path
                    rel_path = file_path_obj

                for exclude_pattern in patterns_to_check:
                    # Check both relative and absolute paths
                    if fnmatch(str(rel_path), exclude_pattern) or fnmatch(
                        file_path, exclude_pattern
                    ):
                        should_exclude = True
                        break

                # Mark for removal if not in current files or should be excluded
                if file_path not in current_file_paths or should_exclude:
                    orphaned_files.append(file_path)

            # Remove orphaned files with progress bar
            orphaned_count = 0
            if orphaned_files:
                with tqdm(
                    total=len(orphaned_files),
                    desc="Cleaning orphaned files",
                    unit="file",
                ) as pbar:
                    for file_path in orphaned_files:
                        if self._db.delete_file_completely(file_path):
                            orphaned_count += 1
                            # Clean up the file lock for orphaned file
                            self._cleanup_file_lock(Path(file_path))
                        pbar.update(1)

                logger.info(f"Cleaned up {orphaned_count} orphaned files from database")

            return orphaned_count

        except Exception as e:
            logger.warning(f"Failed to cleanup orphaned files: {e}")
            return 0
