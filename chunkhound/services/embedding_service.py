"""Embedding service for ChunkHound - manages embedding generation and caching."""

import asyncio
from typing import Any

from loguru import logger
from tqdm import tqdm

from chunkhound.core.types.common import ChunkId
from chunkhound.interfaces.database_provider import DatabaseProvider
from chunkhound.interfaces.embedding_provider import EmbeddingProvider

from .base_service import BaseService


class EmbeddingService(BaseService):
    """Service for managing embedding generation, caching, and optimization."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider | None = None,
        embedding_batch_size: int = 1000,
        db_batch_size: int = 5000,
        max_concurrent_batches: int = 8,
        optimization_batch_frequency: int = 1000,
    ):
        """Initialize embedding service.

        Args:
            database_provider: Database provider for persistence
            embedding_provider: Embedding provider for vector generation
            embedding_batch_size: Number of texts per embedding API request
            db_batch_size: Number of records per database transaction
            max_concurrent_batches: Maximum number of concurrent embedding batches
            optimization_batch_frequency: Optimize DB every N batches (provider-aware)
        """
        super().__init__(database_provider)
        self._embedding_provider = embedding_provider
        self._embedding_batch_size = embedding_batch_size
        self._db_batch_size = db_batch_size
        self._max_concurrent_batches = max_concurrent_batches
        self._optimization_batch_frequency = optimization_batch_frequency

    def set_embedding_provider(self, provider: EmbeddingProvider) -> None:
        """Set or update the embedding provider.

        Args:
            provider: New embedding provider implementation
        """
        self._embedding_provider = provider

    async def generate_embeddings_for_chunks(
        self,
        chunk_ids: list[ChunkId],
        chunk_texts: list[str],
        show_progress: bool = True,
    ) -> int:
        """Generate embeddings for a list of chunks.

        Args:
            chunk_ids: List of chunk IDs to generate embeddings for
            chunk_texts: Corresponding text content for each chunk
            show_progress: Whether to show progress bar (default True)

        Returns:
            Number of embeddings successfully generated
        """
        if not self._embedding_provider:
            logger.warning("No embedding provider configured")
            return 0

        if len(chunk_ids) != len(chunk_texts):
            raise ValueError("chunk_ids and chunk_texts must have the same length")

        try:
            logger.debug(f"Generating embeddings for {len(chunk_ids)} chunks")

            # Filter out chunks that already have embeddings
            filtered_chunks = await self._filter_existing_embeddings(
                chunk_ids, chunk_texts
            )

            if not filtered_chunks:
                logger.debug("All chunks already have embeddings")
                return 0

            # Generate embeddings in batches
            total_generated = await self._generate_embeddings_in_batches(
                filtered_chunks, show_progress
            )

            logger.debug(f"Successfully generated {total_generated} embeddings")
            return total_generated

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return 0

    async def generate_missing_embeddings(
        self,
        provider_name: str | None = None,
        model_name: str | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate embeddings for all chunks that don't have them yet.

        Args:
            provider_name: Optional specific provider to generate for
            model_name: Optional specific model to generate for
            exclude_patterns: Optional file patterns to exclude from embedding generation

        Returns:
            Dictionary with generation statistics
        """
        try:
            if not self._embedding_provider:
                return {
                    "status": "error",
                    "error": "No embedding provider configured",
                    "generated": 0,
                }

            # Use provided provider/model or fall back to configured defaults
            target_provider = provider_name or self._embedding_provider.name
            target_model = model_name or self._embedding_provider.model

            # First, just get the count and IDs of chunks without embeddings (fast query)
            chunk_ids_without_embeddings = self._get_chunk_ids_without_embeddings(
                target_provider, target_model, exclude_patterns
            )

            if not chunk_ids_without_embeddings:
                return {
                    "status": "complete",
                    "generated": 0,
                    "message": "All chunks have embeddings",
                }

            # Generate embeddings in streaming fashion (loads chunk content in batches)
            generated_count = await self._generate_embeddings_streaming(
                chunk_ids_without_embeddings
            )

            return {
                "status": "success",
                "generated": generated_count,
                "total_chunks": len(chunk_ids_without_embeddings),
                "provider": target_provider,
                "model": target_model,
            }

        except Exception as e:
            logger.error(f"Failed to generate missing embeddings: {e}")
            return {"status": "error", "error": str(e), "generated": 0}

    async def regenerate_embeddings(
        self, file_path: str | None = None, chunk_ids: list[ChunkId] | None = None
    ) -> dict[str, Any]:
        """Regenerate embeddings for specific files or chunks.

        Args:
            file_path: Optional file path to regenerate embeddings for
            chunk_ids: Optional specific chunk IDs to regenerate

        Returns:
            Dictionary with regeneration statistics
        """
        try:
            if not self._embedding_provider:
                return {
                    "status": "error",
                    "error": "No embedding provider configured",
                    "regenerated": 0,
                }

            # Determine which chunks to regenerate
            if chunk_ids:
                chunks_to_regenerate = self._get_chunks_by_ids(chunk_ids)
            elif file_path:
                chunks_to_regenerate = self._get_chunks_by_file_path(file_path)
            else:
                return {
                    "status": "error",
                    "error": "Must specify either file_path or chunk_ids",
                    "regenerated": 0,
                }

            if not chunks_to_regenerate:
                return {
                    "status": "complete",
                    "regenerated": 0,
                    "message": "No chunks found",
                }

            logger.info(
                f"Regenerating embeddings for {len(chunks_to_regenerate)} chunks"
            )

            # Delete existing embeddings
            provider_name = self._embedding_provider.name
            model_name = self._embedding_provider.model

            chunk_ids_to_regenerate = [chunk["id"] for chunk in chunks_to_regenerate]
            self._delete_embeddings_for_chunks(
                chunk_ids_to_regenerate, provider_name, model_name
            )

            # Generate new embeddings
            chunk_texts = [chunk["code"] for chunk in chunks_to_regenerate]
            regenerated_count = await self.generate_embeddings_for_chunks(
                chunk_ids_to_regenerate, chunk_texts
            )

            return {
                "status": "success",
                "regenerated": regenerated_count,
                "total_chunks": len(chunks_to_regenerate),
                "provider": provider_name,
                "model": model_name,
            }

        except Exception as e:
            logger.error(f"Failed to regenerate embeddings: {e}")
            return {"status": "error", "error": str(e), "regenerated": 0}

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about embeddings in the database.

        Returns:
            Dictionary with embedding statistics by provider and model
        """
        try:
            # Get all embedding tables
            embedding_tables = self._get_all_embedding_tables()

            if not embedding_tables:
                return {
                    "total_embeddings": 0,
                    "total_unique_chunks": 0,
                    "providers": [],
                    "configured_provider": self._embedding_provider.name
                    if self._embedding_provider
                    else None,
                    "configured_model": self._embedding_provider.model
                    if self._embedding_provider
                    else None,
                }

            # Query each table and aggregate results
            all_results = []
            all_chunks = set()

            for table_name in embedding_tables:
                query = f"""
                    SELECT
                        provider,
                        model,
                        dims,
                        COUNT(*) as count,
                        COUNT(DISTINCT chunk_id) as unique_chunks
                    FROM {table_name}
                    GROUP BY provider, model, dims
                    ORDER BY provider, model, dims
                """

                table_results = self._db.execute_query(query)
                all_results.extend(table_results)

                # Get chunk IDs for total unique calculation
                chunk_query = f"SELECT provider, model, chunk_id FROM {table_name}"
                chunk_results = self._db.execute_query(chunk_query)
                all_chunks.update(
                    (row["provider"], row["model"], row["chunk_id"])
                    for row in chunk_results
                )

            # Calculate totals
            total_embeddings = sum(row["count"] for row in all_results)
            total_unique_chunks = len(all_chunks)

            return {
                "total_embeddings": total_embeddings,
                "total_unique_chunks": total_unique_chunks,
                "providers": all_results,
                "configured_provider": self._embedding_provider.name
                if self._embedding_provider
                else None,
                "configured_model": self._embedding_provider.model
                if self._embedding_provider
                else None,
            }

        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {"error": str(e)}

    async def _filter_existing_embeddings(
        self, chunk_ids: list[ChunkId], chunk_texts: list[str]
    ) -> list[tuple[ChunkId, str]]:
        """Filter out chunks that already have embeddings.

        Args:
            chunk_ids: List of chunk IDs
            chunk_texts: Corresponding chunk texts

        Returns:
            List of (chunk_id, text) tuples for chunks without embeddings
        """
        if not self._embedding_provider:
            return []

        provider_name = self._embedding_provider.name
        model_name = self._embedding_provider.model

        # Get existing embeddings from database
        try:
            # Determine table name based on embedding dimensions
            # We need to check what dimensions this provider/model uses
            if hasattr(self._embedding_provider, "get_dimensions"):
                dims = self._embedding_provider.get_dimensions()
            else:
                # Default to 1536 for most embedding models (OpenAI, etc.)
                dims = 1536

            table_name = f"embeddings_{dims}"

            existing_chunk_ids = self._db.get_existing_embeddings(
                chunk_ids=chunk_ids, provider=provider_name, model=model_name
            )
        except Exception as e:
            logger.error(f"Failed to get existing embeddings: {e}")
            existing_chunk_ids = set()

        # Filter out chunks that already have embeddings
        filtered_chunks = []
        for chunk_id, text in zip(chunk_ids, chunk_texts):
            if chunk_id not in existing_chunk_ids:
                filtered_chunks.append((chunk_id, text))

        logger.debug(
            f"Filtered {len(filtered_chunks)} chunks (out of {len(chunk_ids)}) need embeddings"
        )
        return filtered_chunks

    async def _generate_embeddings_in_batches(
        self, chunk_data: list[tuple[ChunkId, str]], show_progress: bool = True
    ) -> int:
        """Generate embeddings for chunks in optimized batches.

        Args:
            chunk_data: List of (chunk_id, text) tuples

        Returns:
            Number of embeddings successfully generated
        """
        if not chunk_data:
            return 0

        # Create token-aware batches immediately (fast operation)
        batches = self._create_token_aware_batches(chunk_data)

        avg_batch_size = (
            sum(len(batch) for batch in batches) / len(batches) if batches else 0
        )
        logger.debug(
            f"Processing {len(batches)} token-aware batches (avg {avg_batch_size:.1f} chunks each)"
        )

        # Track batch count for periodic optimization
        completed_batch_count = 0
        should_optimize = (
            hasattr(self._db, "optimize_tables") 
            and self._optimization_batch_frequency > 0
        )

        # Process batches with concurrency control
        semaphore = asyncio.Semaphore(self._max_concurrent_batches)

        async def process_batch(
            batch: list[tuple[ChunkId, str]], batch_num: int
        ) -> int:
            """Process a single batch of embeddings."""
            async with semaphore:
                try:
                    logger.debug(
                        f"Processing batch {batch_num + 1}/{len(batches)} with {len(batch)} chunks"
                    )

                    # Extract chunk IDs and texts
                    chunk_ids = [chunk_id for chunk_id, _ in batch]
                    texts = [text for _, text in batch]

                    # Generate embeddings
                    if not self._embedding_provider:
                        return 0
                    embedding_results = await self._embedding_provider.embed(texts)

                    if len(embedding_results) != len(chunk_ids):
                        logger.warning(
                            f"Batch {batch_num}: Expected {len(chunk_ids)} embeddings, got {len(embedding_results)}"
                        )
                        return 0

                    # Prepare embedding data for database
                    embeddings_data = []
                    for chunk_id, vector in zip(chunk_ids, embedding_results):
                        embeddings_data.append(
                            {
                                "chunk_id": chunk_id,
                                "provider": self._embedding_provider.name
                                if self._embedding_provider
                                else "unknown",
                                "model": self._embedding_provider.model
                                if self._embedding_provider
                                else "unknown",
                                "dims": len(vector),
                                "embedding": vector,
                            }
                        )

                    # Store in database with configurable batch size
                    stored_count = self._db.insert_embeddings_batch(
                        embeddings_data, self._db_batch_size
                    )
                    logger.debug(
                        f"Batch {batch_num + 1} completed: {stored_count} embeddings stored"
                    )

                    return stored_count

                except Exception as e:
                    logger.error(f"Batch {batch_num + 1} failed: {e}")
                    return 0

        # Show progress bar only if requested
        if show_progress:
            # Temporarily suppress ALL logs during progress display to prevent flickering
            import io
            import sys

            from loguru import logger as loguru_logger

            # Store current log handlers
            log_handlers = list(loguru_logger._core.handlers.values())

            # Remove all handlers and add a null handler to completely suppress output
            loguru_logger.remove()
            null_stream = io.StringIO()
            loguru_logger.add(null_stream, level="CRITICAL")

            try:
                with tqdm(
                    total=len(chunk_data),
                    desc="Generating embeddings",
                    unit="chunk",
                    position=1,
                    leave=False,
                    dynamic_ncols=True,
                    mininterval=0.2,
                    maxinterval=1.0,
                ) as pbar:
                    # Process batches with limited concurrency and progress tracking
                    import threading

                    update_lock = threading.Lock()

                    async def process_batch_with_progress(
                        batch: list[tuple[ChunkId, str]], batch_num: int
                    ) -> int:
                        result = await process_batch(batch, batch_num)
                        # Thread-safe progress update with rate limiting
                        with update_lock:
                            pbar.update(
                                len(batch)
                            )  # Update progress by number of chunks processed
                        return result

                    # Create tasks with progress tracking
                    tasks = [
                        process_batch_with_progress(batch, i)
                        for i, batch in enumerate(batches)
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                # Restore original logging configuration
                loguru_logger.remove()
                # Restore default stderr handler with INFO level
                loguru_logger.add(sys.stderr, level="INFO")
        else:
            # Process without progress bar
            tasks = [process_batch(batch, i) for i, batch in enumerate(batches)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful embeddings and track completed batches
        total_generated = 0
        successful_batches = 0
        for result in results:
            if isinstance(result, int):
                total_generated += result
                if result > 0:
                    successful_batches += 1
            else:
                logger.error(f"Batch processing exception: {result}")

        # Update completed batch count and run optimization if needed
        if should_optimize and successful_batches > 0:
            completed_batch_count += successful_batches
            
            # Check if we've reached the optimization threshold
            batches_since_last_optimize = completed_batch_count % self._optimization_batch_frequency
            if (
                batches_since_last_optimize < successful_batches 
                or completed_batch_count == self._optimization_batch_frequency
            ):
                logger.debug(
                    f"Running periodic DB optimization after {completed_batch_count} total batches"
                )
                try:
                    self._db.optimize_tables()
                    logger.debug("Periodic optimization completed")
                except Exception as e:
                    logger.warning(f"Periodic optimization failed: {e}")

        return total_generated

    def _create_token_aware_batches(
        self, chunk_data: list[tuple[ChunkId, str]]
    ) -> list[list[tuple[ChunkId, str]]]:
        """Create batches that optimize token utilization while respecting limits.

        This method leverages the embedding provider's token-aware batching if available,
        allowing for optimal batch sizes based on actual token counts rather than
        fixed chunk counts.

        Args:
            chunk_data: List of (chunk_id, text) tuples

        Returns:
            List of optimized batches
        """
        if not chunk_data:
            return []

        # Check if provider supports token-aware batching
        if self._embedding_provider and hasattr(
            self._embedding_provider, "create_token_aware_batches"
        ):
            # Extract texts for provider batching
            texts = [text for _, text in chunk_data]

            try:
                # Use provider's token-aware batching
                text_batches = self._embedding_provider.create_token_aware_batches(
                    texts
                )

                # Reconstruct batches with chunk IDs
                batches = []
                text_idx = 0

                for batch_texts in text_batches:
                    batch = []
                    for _ in batch_texts:
                        if text_idx < len(chunk_data):
                            batch.append(chunk_data[text_idx])
                            text_idx += 1
                    if batch:  # Only add non-empty batches
                        batches.append(batch)

                logger.debug(
                    f"Created {len(batches)} token-aware batches from {len(chunk_data)} chunks"
                )
                return batches

            except Exception as e:
                logger.warning(
                    f"Failed to use provider's token-aware batching: {e}. Falling back to default batching."
                )

        # Fallback: Use configurable batch size from provider or default
        if self._embedding_provider and hasattr(self._embedding_provider, "batch_size"):
            batch_size = self._embedding_provider.batch_size
        else:
            # Default batch size - much more reasonable than 10
            batch_size = (
                self._embedding_batch_size
            )  # Uses the service's configured batch size (default: 100)

        batches = []
        for i in range(0, len(chunk_data), batch_size):
            batch = chunk_data[i : i + batch_size]
            batches.append(batch)

        logger.debug(
            f"Created {len(batches)} fixed-size batches (size={batch_size}) from {len(chunk_data)} chunks"
        )
        return batches

    def _get_chunk_ids_without_embeddings(
        self, provider: str, model: str, exclude_patterns: list[str] | None = None
    ) -> list[ChunkId]:
        """Get just the IDs of chunks that don't have embeddings (provider-agnostic)."""
        # Get all chunks with metadata using provider-agnostic method
        all_chunks = self._db.get_all_chunks_with_metadata()

        # Apply exclude patterns filter using fnmatch (no SQL dependency)
        if exclude_patterns:
            import fnmatch

            filtered_chunks = []
            for chunk in all_chunks:
                file_path = chunk.get("file_path", "")
                should_exclude = False
                for pattern in exclude_patterns:
                    if fnmatch.fnmatch(file_path, pattern):
                        should_exclude = True
                        break
                if not should_exclude:
                    filtered_chunks.append(chunk)
            all_chunks = filtered_chunks

        all_chunk_ids = [chunk.get("chunk_id", chunk.get("id")) for chunk in all_chunks]

        if not all_chunk_ids:
            return []

        # Use provider-agnostic get_existing_embeddings to check which chunks already have embeddings
        existing_chunk_ids = self._db.get_existing_embeddings(
            chunk_ids=all_chunk_ids, provider=provider, model=model
        )

        # Return only chunks that don't have embeddings
        return [
            chunk_id for chunk_id in all_chunk_ids if chunk_id not in existing_chunk_ids
        ]

    async def _generate_embeddings_streaming(self, chunk_ids: list[ChunkId]) -> int:
        """Generate embeddings for chunks by streaming data in batches."""
        if not chunk_ids or not self._embedding_provider:
            return 0

        total_generated = 0
        BATCH_SIZE = 100  # Process 100 chunks at a time to avoid memory issues
        
        # Track batch count for periodic optimization
        batch_count = 0
        should_optimize = (
            hasattr(self._db, "optimize_tables") 
            and self._optimization_batch_frequency > 0
        )

        # Show progress bar immediately
        with tqdm(
            total=len(chunk_ids), desc="Generating embeddings", unit="chunk"
        ) as pbar:
            for i in range(0, len(chunk_ids), BATCH_SIZE):
                batch_ids = chunk_ids[i : i + BATCH_SIZE]

                # Load chunk content for this batch only
                chunks_data = self._get_chunks_by_ids(batch_ids)
                if not chunks_data:
                    pbar.update(len(batch_ids))
                    continue

                # Extract IDs and texts
                chunk_id_list = [chunk["id"] for chunk in chunks_data]
                chunk_texts = [chunk["code"] for chunk in chunks_data]

                # Generate embeddings for this batch (without inner progress bar)
                generated_count = await self.generate_embeddings_for_chunks(
                    chunk_id_list, chunk_texts, show_progress=False
                )
                total_generated += generated_count
                
                # Increment batch counter
                if generated_count > 0:
                    batch_count += 1
                    
                    # Periodic optimization (provider-aware)
                    if (
                        should_optimize 
                        and batch_count > 0 
                        and batch_count % self._optimization_batch_frequency == 0
                    ):
                        logger.debug(
                            f"Running periodic DB optimization after {batch_count} batches"
                        )
                        try:
                            self._db.optimize_tables()
                            logger.debug("Periodic optimization completed")
                        except Exception as e:
                            logger.warning(f"Periodic optimization failed: {e}")

                # Update progress
                pbar.update(len(batch_ids))

        return total_generated

    def _get_chunks_without_embeddings(
        self, provider: str, model: str
    ) -> list[dict[str, Any]]:
        """Get chunks that don't have embeddings for the specified provider/model."""
        # Get all embedding tables
        embedding_tables = self._get_all_embedding_tables()

        if not embedding_tables:
            # No embedding tables exist, return all chunks (but fetch IDs first for progress)
            query = """
                SELECT c.id
                FROM chunks c
                ORDER BY c.id
            """
            chunk_ids_result = self._db.execute_query(query)
            chunk_ids = [row["id"] for row in chunk_ids_result]

            # Now fetch full data
            if chunk_ids:
                return self._get_chunks_by_ids(chunk_ids)
            return []

        # Build NOT EXISTS clauses for all embedding tables
        not_exists_clauses = []
        for table_name in embedding_tables:
            not_exists_clauses.append(f"""
                NOT EXISTS (
                    SELECT 1 FROM {table_name} e
                    WHERE e.chunk_id = c.id
                    AND e.provider = ?
                    AND e.model = ?
                )
            """)

        # First get just the IDs (much faster query)
        query = f"""
            SELECT c.id
            FROM chunks c
            WHERE {" AND ".join(not_exists_clauses)}
            ORDER BY c.id
        """

        # Parameters need to be repeated for each table
        params = [provider, model] * len(embedding_tables)
        chunk_ids_result = self._db.execute_query(query, params)
        chunk_ids = [row["id"] for row in chunk_ids_result]

        # Now fetch full data for these chunks
        if chunk_ids:
            return self._get_chunks_by_ids(chunk_ids)
        return []

    def _get_chunks_by_ids(self, chunk_ids: list[ChunkId]) -> list[dict[str, Any]]:
        """Get chunk data for specific chunk IDs."""
        if not chunk_ids:
            return []

        # Use provider-agnostic method to get all chunks with metadata
        all_chunks_data = self._db.get_all_chunks_with_metadata()

        # Filter to only the requested chunk IDs
        chunk_id_set = set(chunk_ids)
        filtered_chunks = []

        for chunk in all_chunks_data:
            chunk_id = chunk.get("chunk_id", chunk.get("id"))
            if chunk_id in chunk_id_set:
                # Ensure we have the expected fields
                filtered_chunk = {
                    "id": chunk_id,
                    "code": chunk.get(
                        "content", chunk.get("code", "")
                    ),  # LanceDB uses 'content'
                    "symbol": chunk.get(
                        "name", chunk.get("symbol", "")
                    ),  # LanceDB uses 'name'
                    "path": chunk.get("file_path", ""),
                }
                filtered_chunks.append(filtered_chunk)

        return filtered_chunks

    def _get_chunks_by_file_path(self, file_path: str) -> list[dict[str, Any]]:
        """Get all chunks for a specific file path."""
        query = """
            SELECT c.id, c.code, c.symbol, f.path
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.path = ?
            ORDER BY c.id
        """

        return self._db.execute_query(query, [file_path])

    def _delete_embeddings_for_chunks(
        self, chunk_ids: list[ChunkId], provider: str, model: str
    ) -> None:
        """Delete existing embeddings for specific chunks and provider/model."""
        if not chunk_ids:
            return

        # Get all embedding tables and delete from each
        embedding_tables = self._get_all_embedding_tables()

        if not embedding_tables:
            logger.debug("No embedding tables found, nothing to delete")
            return

        placeholders = ",".join("?" for _ in chunk_ids)
        deleted_count = 0

        for table_name in embedding_tables:
            query = f"""
                DELETE FROM {table_name}
                WHERE chunk_id IN ({placeholders})
                AND provider = ?
                AND model = ?
            """

            params = chunk_ids + [provider, model]
            try:
                # Execute the deletion for this table
                self._db.execute_query(query, params)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete from {table_name}: {e}")

        logger.debug(
            f"Deleted existing embeddings for {len(chunk_ids)} chunks from {deleted_count} tables"
        )

    def _get_all_embedding_tables(self) -> list[str]:
        """Get list of all embedding tables (dimension-specific)."""
        try:
            tables = self._db.execute_query("""
                SELECT table_name FROM information_schema.tables
                WHERE table_name LIKE 'embeddings_%'
            """)
            return [table["table_name"] for table in tables]
        except Exception as e:
            logger.error(f"Failed to get embedding tables: {e}")
            return []
