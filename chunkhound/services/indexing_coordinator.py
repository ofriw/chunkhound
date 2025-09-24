"""Indexing coordinator service for ChunkHound - orchestrates indexing workflows.

# FILE_CONTEXT: Central orchestrator for the parse→chunk→embed→store pipeline
# ROLE: Coordinates complex multi-phase workflows with different concurrency models
# CRITICAL: Handles file-level locking and transaction boundaries
# PERFORMANCE: Smart chunk diffing preserves existing embeddings (10x speedup)
"""

import asyncio
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from loguru import logger
from rich.progress import Progress, TaskID

from chunkhound.core.models import File
from chunkhound.core.types.common import FileId, FilePath, Language
from chunkhound.interfaces.database_provider import DatabaseProvider
from chunkhound.interfaces.embedding_provider import EmbeddingProvider
from chunkhound.parsers.universal_parser import UniversalParser

from .base_service import BaseService
from .chunk_cache_service import ChunkCacheService


class IndexingCoordinator(BaseService):
    """Coordinates file indexing workflows with parsing, chunking, and embeddings.

    # CLASS_CONTEXT: Orchestrates the three-phase indexing process
    # RELATIONSHIP: Uses -> LanguageParser, ChunkCacheService, DatabaseProvider
    # CONCURRENCY_MODEL:
    #   - Parse: CPU-bound, can parallelize across files
    #   - Embed: IO-bound, rate-limited batching
    #   - Store: Serial execution required (DB constraint)
    # TRANSACTION_SAFETY: All DB operations wrapped in transactions
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        base_directory: Path,
        embedding_provider: EmbeddingProvider | None = None,
        language_parsers: dict[Language, UniversalParser] | None = None,
        progress: Progress | None = None,
    ):
        """Initialize indexing coordinator.

        Args:
            database_provider: Database provider for persistence
            base_directory: Base directory for path normalization (always set)
            embedding_provider: Optional embedding provider for vector generation
            language_parsers: Optional mapping of language to parser implementations
            progress: Optional Rich Progress instance for hierarchical progress display
        """
        super().__init__(database_provider)
        self._embedding_provider = embedding_provider
        self.progress = progress
        self._language_parsers = language_parsers or {}

        # Performance optimization: shared instances
        self._parser_cache: dict[Language, UniversalParser] = {}

        # Chunk cache service for content-based comparison
        self._chunk_cache = ChunkCacheService()

        # SECTION: File_Level_Locking
        # CRITICAL: Prevents race conditions during concurrent file processing
        # PATTERN: Lazy lock creation within event loop context
        # WHY: asyncio.Lock() must be created inside the event loop
        self._file_locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = None  # Will be initialized when first needed

        # Base directory for path normalization (immutable after initialization)
        # Store raw path - will resolve at usage time for consistent symlink handling
        self._base_directory: Path = base_directory

    def _get_relative_path(self, file_path: Path) -> Path:
        """Get relative path with consistent symlink resolution.

        Resolves both file path and base directory at the same time to ensure
        consistent symlink handling, preventing ValueError on Ubuntu CI systems
        where temporary directories often involve symlinks.
        """
        resolved_file = file_path.resolve()
        resolved_base = self._base_directory.resolve()
        return resolved_file.relative_to(resolved_base)

    def add_language_parser(self, language: Language, parser: UniversalParser) -> None:
        """Add or update a language parser.

        Args:
            language: Programming language identifier
            parser: Parser implementation for the language
        """
        self._language_parsers[language] = parser
        # Clear cache for this language
        if language in self._parser_cache:
            del self._parser_cache[language]

    def get_parser_for_language(self, language: Language) -> UniversalParser | None:
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

        # PATTERN: Double-checked locking for thread-safe lazy initialization
        # CONSTRAINT: asyncio.Lock() must be created in event loop context
        # EDGE_CASE: First call initializes _locks_lock itself

        Args:
            file_path: Path to the file

        Returns:
            AsyncIO lock for the file
        """
        # Initialize the locks lock if needed (first time, in event loop context)
        if self._locks_lock is None:
            self._locks_lock = asyncio.Lock()

        # Use resolve() instead of absolute() to handle symlinks consistently
        file_key = str(file_path.resolve())

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
        # Use resolve() instead of absolute() to handle symlinks consistently
        file_key = str(file_path.resolve())
        if file_key in self._file_locks:
            del self._file_locks[file_key]
            logger.debug(f"Cleaned up lock for deleted file: {file_key}")

    async def process_file(
        self, file_path: Path, skip_embeddings: bool = False
    ) -> dict[str, Any]:
        """Process a single file through the complete indexing pipeline.

        # ENTRY_POINT: Main public API for file processing
        # WORKFLOW: Acquire lock → Parse → Chunk → Store → Generate embeddings
        # CONSTRAINT: One file processed at a time (file-level locking)
        # OPTIMIZATION: skip_embeddings=True for batch processing

        Args:
            file_path: Path to the file to process
            skip_embeddings: If True, skip embedding generation for batch processing

        Returns:
            Dictionary with processing results including status, chunks, and embeddings
        """
        # CRITICAL: File-level locking prevents concurrent modification
        # PATTERN: All processing happens inside the lock
        # PREVENTS: Race conditions, partial updates, data corruption
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

            # Skip large JSON data files (config files are typically < 20KB)
            if language == Language.JSON:
                file_size_kb = file_path.stat().st_size / 1024
                if file_size_kb > 20:  # 20KB threshold
                    return {
                        "status": "skipped",
                        "reason": "large_json_file",
                        "chunks": 0,
                    }

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

            # DESIGN_DECISION: No timestamp checking here
            # RATIONALE: Change detection handled externally
            # BENEFIT: Simpler logic, single responsibility

            # SECTION: Parse_Phase (CPU_BOUND)
            # PATTERN: UniversalParser returns List[Chunk] directly
            # CONSTRAINT: Tree-sitter parsing is thread-safe
            chunks_list = parser.parse_file(file_path, FileId(0))
            if not chunks_list:
                return {"status": "no_content", "chunks": 0}

            if not chunks_list:
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
            # Use consistent symlink-safe path resolution
            relative_path = self._get_relative_path(file_path)
            existing_file = self._db.get_file_by_path(relative_path.as_posix())

            # SECTION: Smart_Chunk_Update (PERFORMANCE_CRITICAL)
            # PATTERN: Diff-based updates preserve unchanged embeddings
            # BENEFIT: 10x speedup by avoiding re-embedding unchanged code
            if existing_file:
                # BUG_FIX: Always clean up old chunks to prevent stale data
                # ISSUE: Content deletion bug when chunks persist after modification

                # UniversalParser already returns Chunk models - create new with correct file_id
                from chunkhound.core.models import Chunk

                new_chunk_models = []
                for chunk in chunks_list:
                    new_chunk = Chunk(
                        file_id=FileId(file_id),
                        symbol=chunk.symbol,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        code=chunk.code,
                        chunk_type=chunk.chunk_type,
                        language=chunk.language,
                        parent_header=chunk.parent_header,
                    )
                    new_chunk_models.append(new_chunk)

                # SECTION: Transaction_Boundary (CRITICAL)
                # PATTERN: All-or-nothing updates prevent partial states
                # RECOVERY: Rollback on any error
                try:
                    self._db.begin_transaction()

                    # RACE_CONDITION_FIX: Read inside transaction
                    # PREVENTS: Duplicate insertions from concurrent processes
                    # ENSURES: Consistent view of current state
                    existing_chunks = self._db.get_chunks_by_file_id(
                        file_id, as_model=True
                    )

                    # ALWAYS process existing files with transaction safety, regardless of existing_chunks
                    # This fixes the content deletion bug where old chunks persist when existing_chunks is empty
                    logger.debug(
                        f"Processing existing file with {len(existing_chunks)} existing chunks"
                    )

                    if existing_chunks:
                        # OPTIMIZATION: Content-based diff preserves embeddings
                        # ALGORITHM: Compares chunk content, not just positions
                        # RESULT: unchanged, added, modified, deleted chunks
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

                        # Check which unchanged chunks are missing embeddings
                        if (
                            not skip_embeddings
                            and chunk_diff.unchanged
                            and self._embedding_provider
                        ):
                            unchanged_chunk_ids = [
                                chunk.id
                                for chunk in chunk_diff.unchanged
                                if chunk.id is not None
                            ]

                            # Use existing interface to check embedding status
                            existing_embedding_ids = self._db.get_existing_embeddings(
                                unchanged_chunk_ids,
                                self._embedding_provider.name,
                                self._embedding_provider.model,
                            )

                            # Find unchanged chunks that need embeddings
                            unchanged_needing_embeddings = [
                                chunk
                                for chunk in chunk_diff.unchanged
                                if chunk.id not in existing_embedding_ids
                            ]

                            # Add to embedding generation lists
                            chunks_needing_embeddings = chunks_to_store + [
                                chunk.to_dict()
                                for chunk in unchanged_needing_embeddings
                            ]
                            chunk_ids_needing_embeddings = chunk_ids_new + [
                                chunk.id for chunk in unchanged_needing_embeddings
                            ]

                            if unchanged_needing_embeddings:
                                logger.debug(
                                    f"Found {len(unchanged_needing_embeddings)} unchanged chunks "
                                    f"missing embeddings - adding to generation queue"
                                )
                        else:
                            # Original logic for skip_embeddings=True or no unchanged chunks
                            chunks_needing_embeddings = chunks_to_store
                            chunk_ids_needing_embeddings = chunk_ids_new

                        logger.debug(
                            f"Smart chunk update complete: {len(chunk_diff.unchanged)} preserved, "
                            f"{len(chunk_diff.added)} added, {len(chunk_diff.modified)} modified, "
                            f"{len(chunk_diff.deleted)} deleted"
                        )
                    else:
                        # No existing chunks found - proceed with fresh insertion
                        # Transaction read shows no chunks, so trust the transactional view
                        logger.debug(
                            f"No existing chunks found for file_id {file_id}, proceeding with fresh insertion"
                        )

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
                from chunkhound.core.models import Chunk

                chunk_models = []
                for chunk in chunks_list:
                    new_chunk = Chunk(
                        file_id=FileId(file_id),
                        symbol=chunk.symbol,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        code=chunk.code,
                        chunk_type=chunk.chunk_type,
                        language=chunk.language,
                        parent_header=chunk.parent_header,
                    )
                    chunk_models.append(new_chunk)
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
                "chunks": len(chunks_list),
                "chunk_ids": chunk_ids,
                "embeddings": embeddings_generated,
                "embeddings_skipped": skip_embeddings,
            }

            # Include chunk data for batch processing
            if skip_embeddings:
                result["chunk_data"] = [chunk.to_dict() for chunk in chunks_list]

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

        # METHOD_CONTEXT: Legacy transaction pattern using backup tables
        # PATTERN: Create backup → Modify → Commit/Rollback → Cleanup
        # WARNING: Complex pattern - prefer simple transactions
        # ALTERNATIVE: Use database-native transaction support

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

            # Create progress task for file processing
            file_task: TaskID | None = None
            if self.progress:
                file_task = self.progress.add_task(
                    "  └─ Processing files", total=len(files), speed="", info=""
                )

            for file_path in files:
                result = await self.process_file(file_path, skip_embeddings=True)

                if result["status"] in ["success", "up_to_date"]:
                    total_files += 1
                    total_chunks += result["chunks"]
                    if file_task is not None and self.progress:
                        self.progress.advance(file_task, 1)
                        self.progress.update(file_task, info=f"{total_chunks} chunks")
                elif result["status"] in ["skipped", "no_content", "no_chunks"]:
                    # Still update progress for skipped files
                    if file_task is not None and self.progress:
                        self.progress.advance(file_task, 1)
                else:
                    # Log errors but continue processing
                    logger.warning(
                        f"Failed to process {file_path}: {result.get('error', 'unknown error')}"
                    )
                    if file_task is not None and self.progress:
                        self.progress.advance(file_task, 1)

            # Complete the file processing progress bar
            if file_task is not None and self.progress:
                task = self.progress.tasks[file_task]
                if task.total:
                    self.progress.update(file_task, completed=task.total)

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
        # Use consistent symlink-safe path resolution
        relative_path = self._get_relative_path(file_path)
        existing_file = self._db.get_file_by_path(relative_path.as_posix())

        if existing_file:
            # Update existing file with new metadata
            if isinstance(existing_file, dict) and "id" in existing_file:
                file_id = existing_file["id"]
                self._db.update_file(
                    file_id, size_bytes=file_stat.st_size, mtime=file_stat.st_mtime
                )
                return file_id

        # Create new File model instance with relative path
        # Use consistent symlink-safe path resolution
        relative_path = self._get_relative_path(file_path)
        file_model = File(
            path=FilePath(relative_path.as_posix()),
            size_bytes=file_stat.st_size,
            mtime=file_stat.st_mtime,
            language=language,
        )
        return self._db.insert_file(file_model)

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
            # Convert path to relative format for database lookup
            file_path_obj = Path(file_path)
            if file_path_obj.is_absolute():
                base_dir = self._base_directory
                relative_path = file_path_obj.relative_to(base_dir).as_posix()
            else:
                relative_path = file_path_obj.as_posix()

            # Get file record to get chunk count before deletion
            file_record = self._db.get_file_by_path(relative_path)
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
            success = self._db.delete_file_completely(relative_path)

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
                optimization_batch_frequency=optimization_batch_frequency,
                progress=self.progress,
            )

            return await embedding_service.generate_missing_embeddings(
                exclude_patterns=exclude_patterns
            )

        except Exception as e:
            # Debug log to trace if this is the mystery error source
            import os
            from datetime import datetime

            debug_file = os.getenv("CHUNKHOUND_DEBUG_FILE", "/tmp/chunkhound_debug.log")
            timestamp = datetime.now().isoformat()
            try:
                with open(debug_file, "a") as f:
                    f.write(
                        f"[{timestamp}] [COORDINATOR-MISSING] Failed to generate missing embeddings: {e}\n"
                    )
                    f.flush()
            except Exception:
                pass

            logger.error(
                f"[IndexCoord-Missing] Failed to generate missing embeddings: {e}"
            )
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
                from chunkhound.utils.normalization import normalize_content

                text = normalize_content(chunk.get("code", ""))
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
            # Log chunk details for debugging oversized chunks
            text_sizes = [len(text) for text in texts] if "texts" in locals() else []
            max_chars = max(text_sizes) if text_sizes else 0
            logger.error(
                f"[IndexCoord] Failed to generate embeddings (chunks: {len(text_sizes)}, max_chars: {max_chars}): {e}"
            )
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
            from chunkhound.core.config.config import Config

            config = Config.from_environment(directory)
            exclude_patterns = config.indexing.exclude

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
        # Resolve directory path once at the beginning for consistent comparison
        directory = directory.resolve()
        files = []

        # Cache for .gitignore patterns by directory
        gitignore_patterns: dict[Path, list[str]] = {}

        def should_exclude_path(
            path: Path, base_dir: Path, patterns: list[str] | None = None
        ) -> bool:
            """Check if a path should be excluded based on exclude patterns."""
            if patterns is None:
                patterns = exclude_patterns

            try:
                rel_path = path.relative_to(base_dir)
            except ValueError:
                # Path is not under base directory, use absolute path as fallback
                rel_path = path

            for exclude_pattern in patterns:
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
            # With directory resolved at start, all paths from iterdir will be consistent
            rel_path = file_path.relative_to(directory)

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
                # Load .gitignore for this directory if it exists
                gitignore_path = current_dir / ".gitignore"
                if gitignore_path.exists():
                    try:
                        with open(
                            gitignore_path, encoding="utf-8", errors="ignore"
                        ) as f:
                            lines = f.read().splitlines()
                        # Filter out comments and empty lines, convert to exclude patterns
                        # Gitignore patterns are converted to our exclude format:
                        # - Patterns starting with / are relative to the gitignore's directory
                        # - Other patterns apply recursively from that point
                        patterns_from_gitignore = []
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Convert gitignore pattern to our exclude pattern format
                                # Patterns starting with / are relative to this directory
                                if line.startswith("/"):
                                    # Make it relative to the root directory we're indexing
                                    rel_from_root = current_dir.relative_to(directory)
                                    if rel_from_root == Path("."):
                                        patterns_from_gitignore.append(line[1:])
                                    else:
                                        patterns_from_gitignore.append(
                                            str(rel_from_root / line[1:])
                                        )
                                else:
                                    # Pattern applies recursively from this directory
                                    # Simple patterns like *.log should match at any level
                                    rel_from_root = current_dir.relative_to(directory)
                                    if rel_from_root == Path("."):
                                        # Pattern at root - just use as is for simple patterns
                                        patterns_from_gitignore.append(line)
                                        # Also add recursive version for patterns like *.log
                                        if "*" in line and not line.startswith("**/"):
                                            patterns_from_gitignore.append(f"**/{line}")
                                    else:
                                        patterns_from_gitignore.append(
                                            f"{rel_from_root}/**/{line}"
                                        )
                                        patterns_from_gitignore.append(
                                            f"{rel_from_root}/{line}"
                                        )
                        gitignore_patterns[current_dir] = patterns_from_gitignore
                    except OSError as e:
                        # Log error but continue - don't fail indexing due to gitignore issues
                        if self.progress_callback:
                            self.progress_callback(
                                f"Warning: Failed to read .gitignore at {gitignore_path}: {e}"
                            )
                    except Exception as e:
                        # Unexpected error - still log but continue
                        if self.progress_callback:
                            self.progress_callback(
                                f"Warning: Unexpected error reading .gitignore at {gitignore_path}: {e}"
                            )

                # Combine all applicable gitignore patterns from this dir and parents
                all_gitignore_patterns = []
                check_dir = current_dir
                while check_dir >= directory:
                    if check_dir in gitignore_patterns:
                        all_gitignore_patterns.extend(gitignore_patterns[check_dir])
                    if check_dir == directory:
                        break
                    check_dir = check_dir.parent

                # Get directory contents
                for entry in current_dir.iterdir():
                    # Skip if path should be excluded by config patterns
                    if should_exclude_path(entry, directory):
                        continue

                    # Skip if path should be excluded by gitignore patterns
                    if all_gitignore_patterns:
                        skip = False
                        for pattern in all_gitignore_patterns:
                            if should_exclude_path(entry, directory, [pattern]):
                                skip = True
                                break
                        if skip:
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
            # Create set of relative paths for fast lookup
            base_dir = self._base_directory
            current_file_paths = {
                file_path.relative_to(base_dir).as_posix()
                for file_path in current_files
            }

            # Get all files in database (stored as relative paths)
            query = """
                SELECT id, path
                FROM files
            """
            db_files = self._db.execute_query(query, [])

            # Find orphaned files (in DB but not on disk or excluded by patterns)
            orphaned_files = []
            if not exclude_patterns:
                from chunkhound.core.config.config import Config

                config = Config.from_environment()
                patterns_to_check = config.indexing.get_default_exclude_patterns()
            else:
                patterns_to_check = exclude_patterns

            for db_file in db_files:
                file_path = db_file["path"]

                # Check if file should be excluded based on current patterns
                should_exclude = False

                # File path is already relative (stored as relative with forward slashes)
                rel_path = Path(file_path)

                for exclude_pattern in patterns_to_check:
                    # Check relative path pattern
                    if fnmatch(str(rel_path), exclude_pattern):
                        should_exclude = True
                        break

                # Mark for removal if not in current files or should be excluded
                if file_path not in current_file_paths or should_exclude:
                    orphaned_files.append(file_path)

            # Remove orphaned files with progress tracking
            orphaned_count = 0
            if orphaned_files:
                cleanup_task: TaskID | None = None
                if self.progress:
                    cleanup_task = self.progress.add_task(
                        "  └─ Cleaning orphaned files",
                        total=len(orphaned_files),
                        speed="",
                        info="",
                    )

                for file_path in orphaned_files:
                    if self._db.delete_file_completely(file_path):
                        orphaned_count += 1
                        # Clean up the file lock for orphaned file
                        self._cleanup_file_lock(Path(file_path))

                    if cleanup_task is not None and self.progress:
                        self.progress.advance(cleanup_task, 1)

                # Complete the cleanup progress bar
                if cleanup_task is not None and self.progress:
                    task = self.progress.tasks[cleanup_task]
                    if task.total:
                        self.progress.update(cleanup_task, completed=task.total)

                logger.info(f"Cleaned up {orphaned_count} orphaned files from database")

            return orphaned_count

        except Exception as e:
            logger.warning(f"Failed to cleanup orphaned files: {e}")
            return 0
