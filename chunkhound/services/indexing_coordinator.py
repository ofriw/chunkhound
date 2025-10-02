"""Indexing coordinator service for ChunkHound - orchestrates indexing workflows.

# FILE_CONTEXT: Central orchestrator for the parse→chunk→embed→store pipeline
# ROLE: Coordinates complex multi-phase workflows with parallel batch processing
# CONCURRENCY: Parsing parallelized across CPU cores, storage remains single-threaded
# PERFORMANCE: Smart chunk diffing preserves existing embeddings (10x speedup)
"""

import asyncio
import math
import os
from concurrent.futures import ProcessPoolExecutor
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from loguru import logger
from rich.progress import Progress, TaskID

from chunkhound.core.models import Chunk, File
from chunkhound.core.types.common import FilePath, Language
from chunkhound.interfaces.database_provider import DatabaseProvider
from chunkhound.interfaces.embedding_provider import EmbeddingProvider
from chunkhound.parsers.universal_parser import UniversalParser

from .base_service import BaseService
from .batch_processor import ParsedFileResult, process_file_batch
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

        Uses the same parallel batch processing path as process_directory,
        but with a single-file batch for consistency.

        Args:
            file_path: Path to the file to process
            skip_embeddings: If True, skip embedding generation

        Returns:
            Dictionary with processing results including status, chunks, and embeddings
        """
        # CRITICAL: File-level locking prevents concurrent async processing
        # PATTERN: All processing happens inside the lock
        # PREVENTS: Race conditions in read-modify-write operations
        file_lock = await self._get_file_lock(file_path)
        async with file_lock:
            # Use batch processor with single file for consistency
            parsed_results = await self._process_files_in_batches([file_path])

            if not parsed_results:
                return {"status": "error", "chunks": 0, "error": "No results from batch processor"}

            result = parsed_results[0]

            if result.status == "error":
                return {"status": "error", "chunks": 0, "error": result.error}

            if result.status == "skipped":
                return {"status": "skipped", "reason": result.error, "chunks": 0}

            # Store the single file result
            store_result = await self._store_parsed_results([result], file_task=None)

            # Handle tuple return for single-file case
            if isinstance(store_result, tuple):
                stats, file_id = store_result
            else:
                # Should not happen for single file, but handle gracefully
                stats = store_result
                file_id = None

            # Generate embeddings if needed
            if not skip_embeddings and self._embedding_provider:
                if stats["chunk_ids_needing_embeddings"]:
                    await self._generate_embeddings(
                        stats["chunk_ids_needing_embeddings"],
                        [chunk for r in parsed_results for chunk in r.chunks]
                    )

            return_dict = {
                "status": "success" if not stats["errors"] else "error",
                "chunks": stats["total_chunks"],
                "errors": stats["errors"],
                "embeddings_skipped": skip_embeddings,
            }

            # Include file_id for single-file operations
            if file_id is not None:
                return_dict["file_id"] = file_id

            return return_dict

    async def _process_files_in_batches(
        self, files: list[Path], config_file_size_threshold_kb: int = 20
    ) -> list[ParsedFileResult]:
        """Process files in parallel batches across CPU cores.

        # PARALLELIZATION_STRATEGY:
        #   - File parsing: CPU-bound tree-sitter operations (parallelizable)
        #   - Batch processing: Each worker handles multiple files independently
        #   - Result aggregation: Collected in main thread for serial storage
        # CRITICAL: Only parsing is parallel, database operations remain single-threaded

        Each CPU core receives a batch of files and performs the complete
        read→parse→chunk pipeline independently before returning results.

        Args:
            files: List of file paths to process
            config_file_size_threshold_kb: Skip structured config files (JSON/YAML/TOML) larger than this (KB)

        Returns:
            List of ParsedFileResult objects with parsed chunks and metadata
        """
        if not files:
            return []

        # Determine number of workers based on CPU count (cap at 8 to prevent resource exhaustion)
        # CONSTRAINT: Limit parallel processes on high-core machines (32+ cores)
        num_workers = min(os.cpu_count() or 4, 8, len(files))

        # Split files into batches for parallel processing
        batch_size = math.ceil(len(files) / num_workers)
        file_batches = [
            files[i : i + batch_size] for i in range(0, len(files), batch_size)
        ]

        # Process batches in parallel using ProcessPoolExecutor
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all batches for concurrent processing
            # Pass config for structured file size filtering (JSON/YAML/TOML)
            config_dict = {"config_file_size_threshold_kb": config_file_size_threshold_kb}
            futures = [
                loop.run_in_executor(
                    executor, process_file_batch, batch, config_dict
                )
                for batch in file_batches
            ]

            # Wait for all batches to complete
            batch_results = await asyncio.gather(*futures)

        # Flatten results from all batches
        all_results = []
        for batch_result in batch_results:
            all_results.extend(batch_result)

        return all_results

    async def _store_parsed_results(
        self, results: list[ParsedFileResult], file_task: TaskID | None = None
    ) -> dict[str, Any] | tuple[dict[str, Any], int]:
        """Store all parsed results in database (single-threaded).

        Args:
            results: List of parsed file results from batch processing
            file_task: Optional progress task ID for tracking

        Returns:
            For multiple files: Dictionary with processing statistics
            For single file: Tuple of (statistics dict, file_id)
        """
        stats = {
            "total_files": 0,
            "total_chunks": 0,
            "errors": [],
            "chunk_ids_needing_embeddings": [],
        }

        # Track file_ids for single-file case
        file_ids = []

        for result in results:
            # Handle errors
            if result.status == "error":
                stats["errors"].append(
                    {"file": str(result.file_path), "error": result.error}
                )
                if file_task is not None and self.progress:
                    self.progress.advance(file_task, 1)
                continue

            # Handle skipped files
            if result.status == "skipped":
                # Track skip reason in stats for single-file case
                if "skip_reason" not in stats:
                    stats["skip_reason"] = result.error
                if file_task is not None and self.progress:
                    self.progress.advance(file_task, 1)
                continue

            # Detect language for storage
            language = result.language

            # Store file record with transaction
            self._db.begin_transaction()
            try:
                # Store file metadata
                file_stat_dict = {
                    "st_size": result.file_size,
                    "st_mtime": result.file_mtime,
                }

                # Create mock stat object for _store_file_record
                class StatResult:
                    def __init__(self, size: int, mtime: float):
                        self.st_size = size
                        self.st_mtime = mtime

                file_stat = StatResult(result.file_size, result.file_mtime)
                file_id = self._store_file_record(result.file_path, file_stat, language)

                # Track file_id for single-file case
                file_ids.append(file_id)

                if file_id is None:
                    self._db.rollback_transaction()
                    stats["errors"].append(
                        {
                            "file": str(result.file_path),
                            "error": "Failed to store file record",
                        }
                    )
                    if file_task is not None and self.progress:
                        self.progress.advance(file_task, 1)
                    continue

                # Check for existing chunks to enable smart diffing
                relative_path = self._get_relative_path(result.file_path)
                existing_file = self._db.get_file_by_path(relative_path.as_posix())

                if existing_file:
                    # Get existing chunks for diffing
                    existing_chunks = self._db.get_chunks_by_file_id(file_id, as_model=True)

                    # Convert result chunks to Chunk models using from_dict()
                    new_chunk_models = [
                        Chunk.from_dict({**chunk_data, "file_id": file_id})
                        for chunk_data in result.chunks
                    ]

                    if existing_chunks:
                        # Smart diff to preserve embeddings
                        chunk_diff = self._chunk_cache.diff_chunks(
                            new_chunk_models, existing_chunks
                        )

                        # Delete modified/removed chunks
                        chunks_to_delete = chunk_diff.deleted + chunk_diff.modified
                        if chunks_to_delete:
                            chunk_ids_to_delete = [
                                chunk.id
                                for chunk in chunks_to_delete
                                if chunk.id is not None
                            ]
                            for chunk_id in chunk_ids_to_delete:
                                self._db.delete_chunk(chunk_id)

                        # Store new/modified chunks (pass models directly)
                        chunks_to_store = chunk_diff.added + chunk_diff.modified

                        if chunks_to_store:
                            chunk_ids_new = self._store_chunks(
                                file_id, chunks_to_store, language
                            )
                        else:
                            chunk_ids_new = []

                        # Track chunks needing embeddings (new + modified)
                        stats["chunk_ids_needing_embeddings"].extend(chunk_ids_new)

                        stats["total_chunks"] += len(result.chunks)
                    else:
                        # No existing chunks - store all as new (pass models directly)
                        chunk_ids = self._store_chunks(file_id, new_chunk_models, language)
                        stats["chunk_ids_needing_embeddings"].extend(chunk_ids)
                        stats["total_chunks"] += len(chunk_ids)
                else:
                    # New file - convert dicts to models, then store
                    chunk_models = [
                        Chunk.from_dict({**chunk_data, "file_id": file_id})
                        for chunk_data in result.chunks
                    ]
                    chunk_ids = self._store_chunks(file_id, chunk_models, language)
                    stats["chunk_ids_needing_embeddings"].extend(chunk_ids)
                    stats["total_chunks"] += len(chunk_ids)

                self._db.commit_transaction()
                stats["total_files"] += 1

                # Update progress
                if file_task is not None and self.progress:
                    self.progress.advance(file_task, 1)
                    self.progress.update(file_task, info=f"{stats['total_chunks']} chunks")

            except Exception as e:
                self._db.rollback_transaction()
                stats["errors"].append({"file": str(result.file_path), "error": str(e)})
                if file_task is not None and self.progress:
                    self.progress.advance(file_task, 1)

        # Return file_id for single-file case
        if len(results) == 1 and file_ids and file_ids[0] is not None:
            return stats, file_ids[0]
        return stats

    async def process_directory(
        self,
        directory: Path,
        patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        config_file_size_threshold_kb: int = 20,
    ) -> dict[str, Any]:
        """Process all supported files in a directory with batch optimization and consistency checks.

        Args:
            directory: Directory path to process
            patterns: Optional file patterns to include
            exclude_patterns: Optional file patterns to exclude
            config_file_size_threshold_kb: Skip structured config files (JSON/YAML/TOML) larger than this (KB)

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

            # Phase 3: Update - Process files in parallel batches
            # Create progress task for file processing
            file_task: TaskID | None = None
            if self.progress:
                file_task = self.progress.add_task(
                    "  └─ Processing files", total=len(files), speed="", info=""
                )

            # Parse files in parallel batches across CPU cores
            parsed_results = await self._process_files_in_batches(files, config_file_size_threshold_kb)

            # Store results in database (single-threaded for safety)
            stats = await self._store_parsed_results(parsed_results, file_task)

            total_files = stats["total_files"]
            total_chunks = stats["total_chunks"]

            # Log any errors
            for error in stats["errors"]:
                logger.warning(f"Failed to process {error['file']}: {error['error']}")

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
            import traceback
            logger.error(f"Failed to process directory {directory}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        self, file_id: int, chunk_models: list[Chunk], language: Language
    ) -> list[int]:
        """Store chunks in database and return chunk IDs.

        Args:
            file_id: File ID for the chunks
            chunk_models: List of Chunk model instances to store
            language: Language (for compatibility, already set in models)

        Returns:
            List of chunk IDs from database insertion
        """
        if not chunk_models:
            return []

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

        # Default exclude patterns if not provided
        if not exclude_patterns:
            exclude_patterns = []

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
                                        # Gitignore patterns without / match recursively by default
                                        if not line.startswith("**/"):
                                            patterns_from_gitignore.append(f"**/{line}")
                                            patterns_from_gitignore.append(f"**/{line}/**")
                                        else:
                                            patterns_from_gitignore.append(line)
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
                        logger.warning(f"Failed to read .gitignore at {gitignore_path}: {e}")
                    except Exception as e:
                        # Unexpected error - still log but continue
                        logger.warning(f"Unexpected error reading .gitignore at {gitignore_path}: {e}")

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
