"""Search service for ChunkHound - handles semantic and regex search operations."""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkId
from chunkhound.interfaces.database_provider import DatabaseProvider
from chunkhound.interfaces.embedding_provider import EmbeddingProvider

from .base_service import BaseService


class SearchService(BaseService):
    """Service for performing semantic and regex searches across indexed code."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize search service.

        Args:
            database_provider: Database provider for data access
            embedding_provider: Optional embedding provider for semantic search
        """
        super().__init__(database_provider)
        self._embedding_provider = embedding_provider

    async def search_semantic(
        self,
        query: str,
        page_size: int = 10,
        offset: int = 0,
        threshold: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        path_filter: str | None = None,
        force_strategy: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform semantic search using vector similarity.

        Automatically selects the best search strategy:
        - Multi-hop + reranking if provider supports reranking
        - Standard single-hop otherwise
        - Can be overridden with force_strategy parameter

        Args:
            query: Natural language search query
            page_size: Number of results per page
            offset: Starting position for pagination
            threshold: Optional similarity threshold to filter results
            provider: Optional specific embedding provider to use
            model: Optional specific model to use
            path_filter: Optional relative path to limit search scope
                (e.g., 'src/', 'tests/')
            force_strategy: Optional strategy override ('single_hop', 'multi_hop')

        Returns:
            Tuple of (results, pagination_metadata)
        """
        try:
            if not self._embedding_provider:
                raise ValueError(
                    "Embedding provider not configured for semantic search"
                )

            # Type narrowing for mypy
            embedding_provider = self._embedding_provider

            # Use provided provider/model or fall back to configured defaults
            search_provider = provider or embedding_provider.name
            search_model = model or embedding_provider.model

            # logger.debug(f"Search using provider='{search_provider}', model='{search_model}'")

            # Choose search strategy based on force_strategy or provider capabilities
            use_multi_hop = False

            if force_strategy == "multi_hop":
                use_multi_hop = True
            elif force_strategy == "single_hop":
                use_multi_hop = False
            else:
                # Auto-select based on provider capabilities
                use_multi_hop = (
                    hasattr(embedding_provider, "supports_reranking")
                    and embedding_provider.supports_reranking()
                )

            if use_multi_hop:
                # Ensure provider actually supports reranking for multi-hop
                if not (
                    hasattr(embedding_provider, "supports_reranking")
                    and embedding_provider.supports_reranking()
                ):
                    logger.warning(
                        "Multi-hop strategy requested but provider doesn't support reranking, falling back to single-hop"
                    )
                    use_multi_hop = False

            if use_multi_hop:
                logger.debug(f"Using multi-hop search with reranking for: '{query}'")
                return await self._search_semantic_multi_hop(
                    query=query,
                    page_size=page_size,
                    offset=offset,
                    threshold=threshold,
                    provider=search_provider,
                    model=search_model,
                    path_filter=path_filter,
                )
            else:
                logger.debug(f"Using standard semantic search for: '{query}'")
                return await self._search_semantic_standard(
                    query=query,
                    page_size=page_size,
                    offset=offset,
                    threshold=threshold,
                    provider=search_provider,
                    model=search_model,
                    path_filter=path_filter,
                )

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise

    async def _search_semantic_standard(
        self,
        query: str,
        page_size: int,
        offset: int,
        threshold: float | None,
        provider: str,
        model: str,
        path_filter: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Standard single-hop semantic search implementation."""
        if not self._embedding_provider:
            raise ValueError("Embedding provider not configured")

        # Generate query embedding
        query_results = await self._embedding_provider.embed([query])
        if not query_results:
            return [], {}

        query_vector = query_results[0]

        # Perform vector similarity search
        results, pagination = self._db.search_semantic(
            query_embedding=query_vector,
            provider=provider,
            model=model,
            page_size=page_size,
            offset=offset,
            threshold=threshold,
            path_filter=path_filter,
        )

        # Enhance results with additional metadata
        enhanced_results = []
        for result in results:
            enhanced_result = self._enhance_search_result(result)
            enhanced_results.append(enhanced_result)

        logger.info(
            f"Standard semantic search completed: {len(enhanced_results)} results found"
        )
        return enhanced_results, pagination

    async def _search_semantic_multi_hop(
        self,
        query: str,
        page_size: int,
        offset: int,
        threshold: float | None,
        provider: str,
        model: str,
        path_filter: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Dynamic multi-hop semantic search with relevance-based termination."""
        import time

        start_time = time.perf_counter()

        # Step 1: Initial search + rerank
        initial_limit = min(page_size * 3, 100)  # Cap at 100 for performance
        initial_results, _ = await self._search_semantic_standard(
            query=query,
            page_size=initial_limit,
            offset=0,
            threshold=0.0,
            provider=provider,
            model=model,
            path_filter=path_filter,
        )

        if len(initial_results) <= 5:
            # Not enough results for expansion, fall back to standard search
            logger.debug(
                "Not enough results for dynamic expansion, using standard search"
            )
            return await self._search_semantic_standard(
                query=query,
                page_size=page_size,
                offset=offset,
                threshold=threshold,
                provider=provider,
                model=model,
                path_filter=path_filter,
            )

        # Rerank initial results
        try:
            assert self._embedding_provider is not None
            assert hasattr(self._embedding_provider, "rerank")

            # Initialize all results with similarity scores as baseline
            for result in initial_results:
                if "score" not in result:
                    result["score"] = result.get("similarity", 0.0)

            documents = [result["content"] for result in initial_results]
            rerank_results = await self._embedding_provider.rerank(
                query=query,
                documents=documents,
                top_k=len(documents),
            )

            # Apply reranking scores (rerank_result.index maps to documents array position)
            for rerank_result in rerank_results:
                if 0 <= rerank_result.index < len(initial_results):
                    initial_results[rerank_result.index]["score"] = rerank_result.score

            # Log reranking effectiveness
            reranked_count = len(rerank_results)
            logger.debug(
                f"Initial reranking: {reranked_count}/{len(initial_results)} results reranked"
            )

            # Sort by rerank score (highest first)
            initial_results = sorted(
                initial_results, key=lambda x: x.get("score", 0.0), reverse=True
            )
        except Exception as e:
            logger.warning(f"Initial reranking failed: {e}")
            # Ensure all results still have scores using similarity as fallback
            for result in initial_results:
                if "score" not in result:
                    result["score"] = result.get("similarity", 0.0)

        # Step 2: Dynamic expansion loop
        all_results = list(initial_results)
        seen_chunk_ids = {result["chunk_id"] for result in initial_results}
        # Track specific chunks and their scores (not positions)
        top_chunk_scores = {}
        for result in initial_results[:5]:
            top_chunk_scores[result["chunk_id"]] = result.get("score", 0.0)

        expansion_round = 0

        while True:
            # Check termination conditions
            if time.perf_counter() - start_time >= 5.0:
                logger.debug(
                    "Dynamic expansion terminated: 5 second time limit reached"
                )
                break
            if len(all_results) >= 500:
                logger.debug("Dynamic expansion terminated: 500 result limit reached")
                break

            # Get top 5 candidates for expansion
            top_candidates = [r for r in all_results if r.get("score", 0.0) > 0.0][:5]
            if len(top_candidates) < 5:
                logger.debug(
                    "Dynamic expansion terminated: insufficient high-scoring candidates"
                )
                break

            # Expand using find_similar_chunks for each top candidate
            new_candidates = []
            for candidate in top_candidates:
                try:
                    # logger.debug(f"Expanding chunk_id={candidate['chunk_id']} using provider='{provider}', model='{model}'")
                    neighbors = self._db.find_similar_chunks(
                        chunk_id=candidate["chunk_id"],
                        provider=provider,
                        model=model,
                        limit=20,  # Get more neighbors per round
                        threshold=None,
                    )

                    # Filter out already seen chunks
                    for neighbor in neighbors:
                        if neighbor["chunk_id"] not in seen_chunk_ids:
                            new_candidates.append(self._enhance_search_result(neighbor))
                            seen_chunk_ids.add(neighbor["chunk_id"])

                    # logger.debug(f"Found {len(neighbors)} neighbors for chunk_id={candidate['chunk_id']}, "
                    #            f"{len([n for n in neighbors if n['chunk_id'] not in seen_chunk_ids])} new")

                except Exception as e:
                    logger.warning(
                        f"Failed to expand chunk {candidate['chunk_id']}: {e}"
                    )
                    # Continue with other candidates even if one fails

            if not new_candidates:
                logger.debug("Dynamic expansion terminated: no new candidates found")
                break

            # Add new candidates and rerank all results
            all_results.extend(new_candidates)

            try:
                # Initialize all results with scores (similarity fallback for new candidates)
                for result in all_results:
                    if "score" not in result:
                        result["score"] = result.get("similarity", 0.0)

                documents = [result["content"] for result in all_results]
                # Type narrowing: we know provider has rerank if we're in multi-hop
                assert self._embedding_provider is not None
                assert hasattr(self._embedding_provider, "rerank")
                rerank_results = await self._embedding_provider.rerank(
                    query=query,
                    documents=documents,
                    top_k=len(documents),
                )

                # Apply reranking scores (rerank_result.index maps to documents array position)
                for rerank_result in rerank_results:
                    if 0 <= rerank_result.index < len(all_results):
                        all_results[rerank_result.index]["score"] = rerank_result.score

                # Log reranking effectiveness
                reranked_count = len(rerank_results)
                logger.debug(
                    f"Expansion reranking: {reranked_count}/{len(all_results)} results reranked"
                )

                # Sort by rerank score
                all_results = sorted(
                    all_results, key=lambda x: x.get("score", 0.0), reverse=True
                )

            except Exception as e:
                logger.warning(
                    f"Reranking failed in expansion round {expansion_round}: {e}"
                )
                # Scores already initialized, just sort and continue
                all_results = sorted(
                    all_results, key=lambda x: x.get("score", 0.0), reverse=True
                )
                break

            # Check score derivative for termination (track specific chunks, not positions)
            current_top_scores = [
                result.get("score", 0.0) for result in all_results[:5]
            ]

            # Check if any of the originally top chunks have degraded significantly
            score_drops = []
            if top_chunk_scores:  # Only check after first iteration
                for chunk_id, prev_score in top_chunk_scores.items():
                    # Find this chunk's current score
                    current_score = next(
                        (
                            r.get("score", 0.0)
                            for r in all_results
                            if r["chunk_id"] == chunk_id
                        ),
                        0.0,  # If not in results anymore, score is 0
                    )
                    if current_score < prev_score:
                        score_drops.append(prev_score - current_score)

            # Update tracked chunks to current top 5
            top_chunk_scores.clear()
            for result in all_results[:5]:
                top_chunk_scores[result["chunk_id"]] = result.get("score", 0.0)

            # Check termination conditions
            if score_drops and max(score_drops) >= 0.15:
                logger.debug(
                    f"Dynamic expansion terminated: tracked chunk score drop "
                    f"{max(score_drops):.3f} >= 0.15"
                )
                break

            if min(current_top_scores) < 0.5:
                logger.debug(
                    f"Dynamic expansion terminated: minimum score "
                    f"{min(current_top_scores):.3f} < 0.5"
                )
                break
            expansion_round += 1

            logger.debug(
                f"Expansion round {expansion_round}: {len(all_results)} total results"
            )

        # Step 3: Final filtering and pagination
        # In multi-hop search, threshold applies to rerank scores (not similarity scores)
        # since rerank scores are the final relevance metric after expansion
        if threshold is not None:
            # Use 0.0 default so unscored results are treated as low relevance, not perfect matches
            all_results = [r for r in all_results if r.get("score", 0.0) >= threshold]
            logger.debug(
                f"Applied rerank score threshold {threshold}, {len(all_results)} results remain"
            )

        # Apply pagination
        total_results = len(all_results)
        paginated_results = all_results[offset : offset + page_size]

        pagination = {
            "offset": offset,
            "page_size": page_size,
            "has_more": offset + page_size < total_results,
            "next_offset": offset + page_size
            if offset + page_size < total_results
            else None,
            "total": total_results,
        }

        elapsed_time = time.perf_counter() - start_time
        logger.info(
            f"Dynamic expansion search completed in {elapsed_time:.2f}s: "
            f"{len(paginated_results)} results returned "
            f"({total_results} total candidates, "
            f"{expansion_round} expansion rounds)"
        )
        return paginated_results, pagination

    def search_regex(
        self,
        pattern: str,
        page_size: int = 10,
        offset: int = 0,
        path_filter: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform regex search on code content.

        Args:
            pattern: Regular expression pattern to search for
            page_size: Number of results per page
            offset: Starting position for pagination
            path_filter: Optional relative path to limit search scope
                (e.g., 'src/', 'tests/')

        Returns:
            Tuple of (results, pagination_metadata)
        """
        try:
            logger.debug(f"Performing regex search for pattern: '{pattern}'")

            # Perform regex search
            results, pagination = self._db.search_regex(
                pattern=pattern,
                page_size=page_size,
                offset=offset,
                path_filter=path_filter,
            )

            # Enhance results with additional metadata
            enhanced_results = []
            for result in results:
                enhanced_result = self._enhance_search_result(result)
                enhanced_results.append(enhanced_result)

            logger.info(
                f"Regex search completed: {len(enhanced_results)} results found"
            )
            return enhanced_results, pagination

        except Exception as e:
            logger.error(f"Regex search failed: {e}")
            raise

    async def search_hybrid(
        self,
        query: str,
        regex_pattern: str | None = None,
        page_size: int = 10,
        offset: int = 0,
        semantic_weight: float = 0.7,
        threshold: float | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Perform hybrid search combining semantic and regex results.

        Args:
            query: Natural language search query
            regex_pattern: Optional regex pattern to include in search
            page_size: Number of results per page
            offset: Starting position for pagination
            semantic_weight: Weight given to semantic results (0.0-1.0)
            threshold: Optional similarity threshold for semantic results

        Returns:
            Tuple of (results, pagination_metadata)
        """
        try:
            logger.debug(
                f"Performing hybrid search: query='{query}', pattern='{regex_pattern}'"
            )

            # Perform searches concurrently
            tasks = []

            # Semantic search
            if self._embedding_provider:
                semantic_task = asyncio.create_task(
                    self.search_semantic(
                        query,
                        page_size=page_size * 2,
                        offset=offset,
                        threshold=threshold,
                    )
                )
                tasks.append(("semantic", semantic_task))

            # Regex search
            if regex_pattern:

                async def get_regex_results() -> tuple[
                    list[dict[str, Any]], dict[str, Any]
                ]:
                    return self.search_regex(
                        regex_pattern, page_size=page_size * 2, offset=offset
                    )

                tasks.append(("regex", asyncio.create_task(get_regex_results())))

            # Wait for all searches to complete
            results_by_type = {}
            pagination_data = {}
            for search_type, task in tasks:
                results, pagination = await task
                results_by_type[search_type] = results
                pagination_data[search_type] = pagination

            # Combine and rank results
            combined_results = self._combine_search_results(
                semantic_results=results_by_type.get("semantic", []),
                regex_results=results_by_type.get("regex", []),
                semantic_weight=semantic_weight,
                limit=page_size,
            )

            # Create combined pagination metadata
            combined_pagination = {
                "offset": offset,
                "page_size": page_size,
                "has_more": len(combined_results) == page_size,
                "next_offset": offset + page_size
                if len(combined_results) == page_size
                else None,
                "total": None,  # Cannot estimate for hybrid search
            }

            logger.info(
                f"Hybrid search completed: {len(combined_results)} results found"
            )
            return combined_results, combined_pagination

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise

    def get_chunk_context(
        self, chunk_id: ChunkId, context_lines: int = 5
    ) -> dict[str, Any]:
        """Get additional context around a specific chunk.

        Args:
            chunk_id: ID of the chunk to get context for
            context_lines: Number of lines before/after to include

        Returns:
            Dictionary with chunk details and surrounding context
        """
        try:
            # Get chunk details
            chunk_query = """
                SELECT c.*, f.path, f.language
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE c.id = ?
            """
            chunk_results = self._db.execute_query(chunk_query, [chunk_id])

            if not chunk_results:
                return {}

            chunk = chunk_results[0]

            # Get surrounding chunks for context
            context_query = """
                SELECT symbol, start_line, end_line, code, chunk_type
                FROM chunks
                WHERE file_id = ?
                AND (
                    (start_line BETWEEN ? AND ?) OR
                    (end_line BETWEEN ? AND ?) OR
                    (start_line <= ? AND end_line >= ?)
                )
                ORDER BY start_line
            """

            start_context = max(1, chunk["start_line"] - context_lines)
            end_context = chunk["end_line"] + context_lines

            context_results = self._db.execute_query(
                context_query,
                [
                    chunk["file_id"],
                    start_context,
                    end_context,
                    start_context,
                    end_context,
                    start_context,
                    end_context,
                ],
            )

            return {
                "chunk": chunk,
                "context": context_results,
                "file_path": chunk["path"],
                "language": chunk["language"],
            }

        except Exception as e:
            logger.error(f"Failed to get chunk context for {chunk_id}: {e}")
            return {}

    def get_file_chunks(self, file_path: str) -> list[dict[str, Any]]:
        """Get all chunks for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            List of chunks in the file ordered by line number
        """
        try:
            query = """
                SELECT c.*, f.language
                FROM chunks c
                JOIN files f ON c.file_id = f.id
                WHERE f.path = ?
                ORDER BY c.start_line
            """

            results = self._db.execute_query(query, [file_path])

            # Enhance results
            enhanced_results = []
            for result in results:
                enhanced_result = self._enhance_search_result(result)
                enhanced_results.append(enhanced_result)

            return enhanced_results

        except Exception as e:
            logger.error(f"Failed to get chunks for file {file_path}: {e}")
            return []

    def _enhance_search_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Enhance search result with additional metadata and formatting.

        Args:
            result: Raw search result from database

        Returns:
            Enhanced result with additional metadata
        """
        enhanced = result.copy()

        # Add computed fields
        if "start_line" in result and "end_line" in result:
            enhanced["line_count"] = result["end_line"] - result["start_line"] + 1

        # Add code preview (truncated if too long)
        if "code" in result and result["code"]:
            code = result["code"]
            if len(code) > 500:
                enhanced["code_preview"] = code[:500] + "..."
                enhanced["is_truncated"] = True
            else:
                enhanced["code_preview"] = code
                enhanced["is_truncated"] = False

        # Add file extension for quick language identification
        if "path" in result:
            file_path = result["path"]
            enhanced["file_extension"] = Path(file_path).suffix.lower()

        # Format similarity score if present
        if "similarity" in result:
            enhanced["similarity_percentage"] = round(result["similarity"] * 100, 2)

        return enhanced

    def _combine_search_results(
        self,
        semantic_results: list[dict[str, Any]],
        regex_results: list[dict[str, Any]],
        semantic_weight: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Combine semantic and regex search results with weighted ranking.

        Args:
            semantic_results: Results from semantic search
            regex_results: Results from regex search
            semantic_weight: Weight for semantic results (0.0-1.0)
            limit: Maximum number of results to return

        Returns:
            Combined and ranked results
        """
        combined = {}
        regex_weight = 1.0 - semantic_weight

        # Process semantic results
        for i, result in enumerate(semantic_results):
            chunk_id = result.get("chunk_id") or result.get("id")
            if chunk_id:
                # Score based on position and similarity
                position_score = (len(semantic_results) - i) / len(semantic_results)
                similarity_score = result.get("similarity", 0.5)
                score = (
                    position_score * 0.3 + similarity_score * 0.7
                ) * semantic_weight

                combined[chunk_id] = {
                    **result,
                    "search_type": "semantic",
                    "combined_score": score,
                    "semantic_score": similarity_score,
                }

        # Process regex results
        for i, result in enumerate(regex_results):
            chunk_id = result.get("chunk_id") or result.get("id")
            if chunk_id:
                # Score based on position (regex has no similarity score)
                position_score = (len(regex_results) - i) / len(regex_results)
                score = position_score * regex_weight

                if chunk_id in combined:
                    # Boost existing result
                    combined[chunk_id]["combined_score"] += score
                    combined[chunk_id]["search_type"] = "hybrid"
                    combined[chunk_id]["regex_score"] = position_score
                else:
                    combined[chunk_id] = {
                        **result,
                        "search_type": "regex",
                        "combined_score": score,
                        "regex_score": position_score,
                    }

        # Sort by combined score and return top results
        sorted_results = sorted(
            combined.values(), key=lambda x: x["combined_score"], reverse=True
        )

        return sorted_results[:limit]
