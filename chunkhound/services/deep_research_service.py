"""Deep Research Service for ChunkHound - BFS-based semantic exploration."""

import asyncio
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.database_factory import DatabaseServices
from chunkhound.embeddings import EmbeddingManager
from chunkhound.llm_manager import LLMManager

# Constants
RELEVANCE_THRESHOLD = 0.5  # Lower threshold for better recall, reranking will filter
NODE_SIMILARITY_THRESHOLD = 0.2  # Reserved for future similarity-based deduplication (currently uses LLM)
MAX_FOLLOWUP_QUESTIONS = 3
MAX_SYMBOLS_TO_SEARCH = 5  # Top N symbols to search via regex (from spec)
QUERY_EXPANSION_ENABLED = True  # Enable LLM-powered query expansion for better recall
NUM_EXPANDED_QUERIES = 3  # Number of diverse queries to generate for semantic search

# Adaptive token budgets (depth-dependent)
ENABLE_ADAPTIVE_BUDGETS = True  # Enable depth-based adaptive budgets

# File content budget range (input: what LLM sees for code)
FILE_CONTENT_TOKENS_MIN = 10_000    # Root nodes (synthesizing, need less raw code)
FILE_CONTENT_TOKENS_MAX = 50_000    # Leaf nodes (analyzing, need full implementations)

# LLM total input budget range (query + context + code)
LLM_INPUT_TOKENS_MIN = 15_000       # Root nodes
LLM_INPUT_TOKENS_MAX = 60_000       # Leaf nodes

# Leaf answer output budget (what LLM generates at leaves)
# NOTE: Reduced from 30k to balance cost vs quality. If you observe:
#   - Frequent "Missing: [detail]" statements
#   - Theoretical placeholders ("provide exact values")
#   - Incomplete analysis of complex components
# Consider increasing these values. Quality validation warnings will indicate budget pressure.
LEAF_ANSWER_TOKENS_BASE = 18_000    # Base budget for leaf nodes (was 30k, reduced for cost)
LEAF_ANSWER_TOKENS_BONUS = 3_000    # Additional tokens for deeper leaves (was 5k, reduced for cost)

# Internal synthesis output budget (what LLM generates at internal nodes)
# NOTE: Reduced from 17.5k/32k to balance cost vs quality. If root synthesis appears rushed or
# omits critical architectural details, consider increasing INTERNAL_ROOT_TARGET.
INTERNAL_ROOT_TARGET = 11_000       # Root synthesis target (was 17.5k, reduced for cost)
INTERNAL_MAX_TOKENS = 19_000        # Maximum for deep internal nodes (was 32k, reduced for cost)

# Legacy constants (used when ENABLE_ADAPTIVE_BUDGETS = False)
TOKEN_BUDGET_PER_FILE = 4000
EXTRA_CONTEXT_TOKENS = 1000
MAX_FILE_CONTENT_TOKENS = 3000
MAX_LLM_INPUT_TOKENS = 5000
MAX_LEAF_ANSWER_TOKENS = 400
MAX_SYNTHESIS_TOKENS = 600

# Single-pass synthesis constants (new architecture)
SINGLE_PASS_MAX_TOKENS = 150_000  # Total budget for single-pass synthesis (input + output)
SINGLE_PASS_OUTPUT_TOKENS = 30_000  # Target/max tokens for synthesis output
SINGLE_PASS_OVERHEAD_TOKENS = 5_000  # Prompt template and overhead
SINGLE_PASS_TIMEOUT_SECONDS = 600  # 10 minutes timeout for large synthesis calls
# Available for code/chunks: 150k - 30k - 5k = 115k tokens

# Output control
REQUIRE_CITATIONS = True  # Validate file:line format

# Smart boundary detection for context-aware file reading
ENABLE_SMART_BOUNDARIES = True  # Expand to natural code boundaries (functions/classes)
MAX_BOUNDARY_EXPANSION_LINES = 300  # Maximum lines to expand for complete functions


@dataclass
class BFSNode:
    """Node in the BFS research graph."""

    query: str
    parent: "BFSNode | None" = None
    depth: int = 0
    children: list["BFSNode"] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    file_contents: dict[str, str] = field(default_factory=dict)  # Full file contents for synthesis
    answer: str | None = None
    node_id: int = 0
    unanswered_aspects: list[str] = field(default_factory=list)  # Questions we couldn't answer
    token_budgets: dict[str, int] = field(default_factory=dict)  # Adaptive token budgets for this node

    # Termination tracking
    is_terminated_leaf: bool = False  # True if terminated due to no new information
    new_chunk_count: int = 0  # Count of truly new chunks
    duplicate_chunk_count: int = 0  # Count of duplicate chunks


@dataclass
class ResearchContext:
    """Context for research traversal."""

    root_query: str
    ancestors: list[str] = field(default_factory=list)
    traversal_path: list[str] = field(default_factory=list)


class DeepResearchService:
    """Service for performing deep research using BFS exploration."""

    def __init__(
        self,
        database_services: DatabaseServices,
        embedding_manager: EmbeddingManager,
        llm_manager: LLMManager,
        tool_name: str = "code_research",
    ):
        """Initialize deep research service.

        Args:
            database_services: Database services bundle
            embedding_manager: Embedding manager for semantic search
            llm_manager: LLM manager for generating follow-ups and synthesis
            tool_name: Name of the MCP tool (used in followup suggestions)
        """
        self._db_services = database_services
        self._embedding_manager = embedding_manager
        self._llm_manager = llm_manager
        self._tool_name = tool_name
        self._node_counter = 0

    async def deep_research(self, query: str) -> dict[str, Any]:
        """Perform deep research on a query.

        Removed user-facing follow-up suggestions from output for cleaner responses.
        Internal BFS exploration still generates follow-ups to drive multi-level search.

        Args:
            query: Research query

        Returns:
            Dictionary with answer and metadata (no follow_up_suggestions)
        """
        logger.info(f"Starting deep research for query: '{query}'")

        # Calculate max depth based on repository size
        max_depth = self._calculate_max_depth()
        logger.info(f"Max depth for this repository: {max_depth}")

        # Initialize BFS graph with root node
        root = BFSNode(query=query, depth=0, node_id=self._get_next_node_id())
        context = ResearchContext(root_query=query)

        # BFS traversal
        current_level = [root]
        all_nodes: list[BFSNode] = [root]

        for depth in range(1, max_depth + 1):
            if not current_level:
                break

            logger.info(f"Processing BFS level {depth}, nodes: {len(current_level)}")

            # Process all nodes at this level concurrently (as per algorithm spec)
            # Each node gets its own context copy to avoid shared state issues
            node_contexts = []
            for node in current_level:
                # Create context copy WITHOUT adding current query to ancestors yet
                # (it will be added to global context AFTER processing)
                # This prevents redundancy in _build_search_query
                node_context = ResearchContext(
                    root_query=context.root_query,
                    ancestors=context.ancestors.copy(),  # Just copy, don't append node.query
                    traversal_path=context.traversal_path.copy(),
                )
                node_contexts.append((node, node_context))

            # Process all nodes concurrently
            node_tasks = [
                self._process_bfs_node(node, node_ctx, depth)
                for node, node_ctx in node_contexts
            ]
            children_lists = await asyncio.gather(*node_tasks, return_exceptions=True)

            # Collect children and handle errors
            next_level: list[BFSNode] = []
            for (node, node_ctx), children_result in zip(node_contexts, children_lists):
                if isinstance(children_result, Exception):
                    logger.error(
                        f"BFS node failed for '{node.query}': {children_result}"
                    )
                    continue

                # Type narrowing: at this point children_result is list[BFSNode]
                assert isinstance(children_result, list)
                node.children.extend(children_result)
                next_level.extend(children_result)
                all_nodes.extend(children_result)

            # Update global context with all processed queries
            for node, _ in node_contexts:
                if node.query not in context.ancestors:
                    context.ancestors.append(node.query)

            # Synthesize questions at this level if too many
            if len(next_level) > MAX_FOLLOWUP_QUESTIONS:
                next_level = await self._synthesize_questions(
                    next_level, context, MAX_FOLLOWUP_QUESTIONS
                )

            current_level = next_level

        # Aggregate all findings from BFS tree
        logger.info("BFS traversal complete, aggregating findings")
        aggregated = self._aggregate_all_findings(root)

        # Manage token budget for single-pass synthesis
        prioritized_chunks, budgeted_files, budget_info = (
            self._manage_token_budget_for_synthesis(
                aggregated["chunks"], aggregated["files"]
            )
        )

        # Single-pass synthesis with all data
        answer = await self._single_pass_synthesis(
            root_query=query,
            chunks=prioritized_chunks,
            files=budgeted_files,
            context=context,
        )

        # Validate output quality (conciseness, actionability)
        llm = self._llm_manager.get_utility_provider()
        target_tokens = llm.estimate_tokens(answer)
        answer, quality_warnings = self._validate_output_quality(answer, target_tokens)
        if quality_warnings:
            logger.warning(f"Quality issues detected:\n" + "\n".join(quality_warnings))

        # Validate citations in answer
        answer = self._validate_citations(answer, root.chunks)

        # Calculate metadata
        metadata = {
            "depth_reached": max(node.depth for node in all_nodes),
            "nodes_explored": len(all_nodes),
            "chunks_analyzed": sum(len(node.chunks) for node in all_nodes),
            "aggregation_stats": aggregated["stats"],
            "token_budget": budget_info,
        }

        logger.info(f"Deep research completed: {metadata}")

        return {
            "answer": answer,
            "metadata": metadata,
        }

    async def _process_bfs_node(
        self, node: BFSNode, context: ResearchContext, depth: int
    ) -> list[BFSNode]:
        """Process a single BFS node.

        Args:
            node: BFS node to process
            context: Research context
            depth: Current depth in graph

        Returns:
            List of child nodes (follow-up questions)
        """
        logger.debug(f"Processing node at depth {depth}: '{node.query}'")

        # Calculate adaptive token budgets for this node (assume leaf initially)
        max_depth = self._calculate_max_depth()
        node.token_budgets = self._get_adaptive_token_budgets(
            depth=depth, max_depth=max_depth, is_leaf=True
        )

        # Step 1: Combine query with BFS ancestors for semantic search
        search_query = self._build_search_query(node.query, context)

        # Step 2-7: Run unified search (semantic + symbol extraction + regex + reranking)
        chunks = await self._unified_search(search_query, context)
        node.chunks = chunks

        if not chunks:
            logger.warning(f"No chunks found for query: '{node.query}'")
            return []

        # Step 8: Read files with adaptive token budget
        file_contents = await self._read_files_with_budget(
            chunks, max_tokens=node.token_budgets["file_content_tokens"]
        )
        node.file_contents = file_contents  # Store for later synthesis

        # Step 8.5: Check for new information (termination rule)
        has_new_info, dedup_stats = self._detect_new_information(node, chunks)
        node.new_chunk_count = dedup_stats["new_chunks"]
        node.duplicate_chunk_count = dedup_stats["duplicate_chunks"]

        if not has_new_info:
            logger.info(
                f"[Termination] Node '{node.query[:50]}...' at depth {depth} "
                f"found 0 new chunks ({dedup_stats['duplicate_chunks']} duplicates). "
                f"Marking as terminated leaf, skipping question generation."
            )
            node.is_terminated_leaf = True
            return []  # No children

        logger.debug(
            f"Node '{node.query[:50]}...' at depth {depth} "
            f"found {dedup_stats['new_chunks']} new chunks, "
            f"{dedup_stats['duplicate_chunks']} duplicates"
        )

        # Step 9: Generate follow-up questions using LLM with adaptive budget
        follow_ups = await self._generate_follow_up_questions(
            node.query,
            context,
            file_contents,
            chunks,
            max_input_tokens=node.token_budgets["llm_input_tokens"],
        )

        # Create child nodes
        children = []
        for i, follow_up in enumerate(follow_ups[:MAX_FOLLOWUP_QUESTIONS]):
            child = BFSNode(
                query=follow_up,
                parent=node,
                depth=depth + 1,  # Children are one level deeper than current depth
                node_id=self._get_next_node_id(),
            )
            children.append(child)

        return children

    def _build_search_query(self, query: str, context: ResearchContext) -> str:
        """Build search query combining input with BFS context.

        Evidence-based design (per research on embedding model position bias):
        - Current query FIRST (embedding models weight beginning 15-50% more heavily)
        - Minimal parent context (last 1-2 ancestors for disambiguation)
        - Clear separator to distinguish query from context
        - Root query implicitly preserved through ancestor chain

        Args:
            query: Current query
            context: Research context with ancestors

        Returns:
            Combined search query optimized for semantic search
        """
        if not context.ancestors:
            # Root node: just the query itself
            return query

        # For child nodes: prioritize current query, add minimal parent context
        # Take last 1-2 ancestors (not more to avoid redundancy)
        parent_context = context.ancestors[-2:] if len(context.ancestors) >= 2 else context.ancestors[-1:]
        context_str = " → ".join(parent_context)

        # Current query FIRST (position bias optimization), then context
        return f"{query} | Context: {context_str}"

    async def _expand_query_with_llm(
        self, query: str, context: ResearchContext
    ) -> list[str]:
        """Expand query into multiple diverse semantic search queries.

        Uses LLM to generate different perspectives on the same question,
        improving recall by casting a wider semantic net.

        Args:
            query: Current query to expand
            context: Research context with root query and ancestors

        Returns:
            List of expanded queries (defaults to [query] if expansion fails)
        """
        llm = self._llm_manager.get_utility_provider()

        system = """You are optimizing queries for CODE SEARCH in a semantic embedding system.
Your goal: reformulate the query to match how code is actually written and documented.
Stay within the CODE DOMAIN - no abstract concepts or unrelated technologies."""

        # Build context string
        context_str = ""
        if context.ancestors:
            ancestor_path = " → ".join(context.ancestors[-2:])
            context_str = f"\nPrior exploration: {ancestor_path}"

        prompt = f"""Original question: {query}
Codebase context: {context.root_query}{context_str}

Generate {NUM_EXPANDED_QUERIES} code search queries for semantic embedding:

INSTRUCTIONS:
Query 1: Output the original question EXACTLY as given (verbatim)
Query 2: Rephrase with code-specific technical terms (add likely function/class names, programming terminology)
Query 3: Describe hypothetical code structure (mention patterns like "class X", "def method()", "calls Y")

RULES:
- All queries must be about CODE in THIS codebase
- NO abstract concepts ("across disciplines", "principles", "paradigms")
- NO unrelated technologies (Docker, MLflow, CI/CD unless actually in codebase)
- Use technical terms that would appear in actual code/comments/docstrings
- Keep each query 1-2 sentences maximum

OUTPUT FORMAT (simple numbered list):
1. [query 1 text here]
2. [query 2 text here]
3. [query 3 text here]

Example:
Input: "How does the authentication system work?"
Output:
1. How does the authentication system work?
2. authentication implementation user login validation middleware
3. Auth class with login() verify_token() methods handling session management"""

        try:
            response = await llm.complete(prompt, system=system, max_completion_tokens=2500)

            # Parse queries from response
            queries = []
            for line in response.content.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    query_text = line.lstrip("0123456789.-) ").strip()
                    if query_text:
                        queries.append(query_text)

            # Ensure we have at least the original query
            if not queries:
                logger.warning("LLM query expansion returned no queries, using original")
                return [query]

            # Take first NUM_EXPANDED_QUERIES, or pad with original if fewer
            while len(queries) < NUM_EXPANDED_QUERIES:
                queries.append(query)

            expanded = queries[:NUM_EXPANDED_QUERIES]
            logger.debug(f"Expanded query into {len(expanded)} variants")
            return expanded

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}, using original query")
            return [query]

    async def _unified_search(
        self, query: str, context: ResearchContext
    ) -> list[dict[str, Any]]:
        """Perform unified semantic + symbol-based regex search with reranking (Steps 2-7).

        Algorithm steps:
        1. Multi-hop semantic search with reranking (Step 2)
        2. Extract symbols from semantic results (Step 3)
        3. Rerank symbols by relevance (Step 4)
        4. Regex search for top symbols (Step 5)
        5. Unify results at chunk level (Step 6)
        6. Final reranking of unified results (Step 7)

        Args:
            query: Search query
            context: Research context with root query and ancestors

        Returns:
            List of unified and reranked chunks
        """
        search_service = self._db_services.search_service

        # Step 2: Multi-hop semantic search with reranking (optionally with query expansion)
        if QUERY_EXPANSION_ENABLED:
            # Expand query into multiple diverse perspectives
            logger.debug("Step 2a: Expanding query for diverse semantic search")
            expanded_queries = await self._expand_query_with_llm(query, context)
            logger.debug(f"Expanded into {len(expanded_queries)} queries: {expanded_queries}")

            # Run all semantic searches in parallel
            logger.debug(f"Step 2b: Running {len(expanded_queries)} parallel semantic searches")
            search_tasks = [
                search_service.search_semantic(
                    query=expanded_q,
                    page_size=30,
                    threshold=RELEVANCE_THRESHOLD,
                    force_strategy="multi_hop",
                )
                for expanded_q in expanded_queries
            ]
            search_results = await asyncio.gather(*search_tasks)

            # Unify results: deduplicate by chunk_id (same pattern as semantic+regex unification)
            semantic_map = {}
            for results, _ in search_results:
                for chunk in results:
                    chunk_id = chunk.get("chunk_id") or chunk.get("id")
                    if chunk_id and chunk_id not in semantic_map:
                        semantic_map[chunk_id] = chunk

            semantic_results = list(semantic_map.values())
            logger.debug(
                f"Unified {sum(len(r[0]) for r in search_results)} results from {len(expanded_queries)} searches -> {len(semantic_results)} unique chunks"
            )
        else:
            # Original single-query approach (fallback)
            logger.debug(f"Step 2: Running multi-hop semantic search for query: '{query}'")
            semantic_results, _ = await search_service.search_semantic(
                query=query,
                page_size=30,
                threshold=RELEVANCE_THRESHOLD,
                force_strategy="multi_hop",
            )
            logger.debug(f"Semantic search returned {len(semantic_results)} chunks")

        # Steps 3-5: Symbol extraction, reranking, and regex search
        regex_results = []
        if semantic_results:
            # Step 3: Extract symbols from semantic results
            logger.debug("Step 3: Extracting symbols from semantic results")
            symbols = await self._extract_symbols_from_chunks(semantic_results)

            if symbols:
                # Step 4: Rerank symbols by relevance
                logger.debug(f"Step 4: Reranking {len(symbols)} symbols")
                top_symbols = await self._rerank_symbols(symbols, query, context)

                if top_symbols:
                    # Step 5: Regex search for top symbols
                    logger.debug(
                        f"Step 5: Running regex search for {len(top_symbols)} top symbols"
                    )
                    regex_results = await self._search_by_symbols(top_symbols)

        # Step 6: Unify results at chunk level (deduplicate by chunk_id)
        logger.debug(
            f"Step 6: Unifying {len(semantic_results)} semantic + {len(regex_results)} regex results"
        )
        unified_map = {}

        # Add semantic results first (they have relevance scores from multi-hop)
        for chunk in semantic_results:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if chunk_id:
                unified_map[chunk_id] = chunk

        # Add regex results (only new chunks not already found)
        for chunk in regex_results:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if chunk_id and chunk_id not in unified_map:
                unified_map[chunk_id] = chunk

        unified_chunks = list(unified_map.values())
        logger.debug(f"Unified to {len(unified_chunks)} unique chunks")

        # Step 7: Final reranking of unified results
        if len(unified_chunks) > 1:
            logger.debug("Step 7: Final reranking of unified results")
            unified_chunks = await self._rerank_unified_chunks(unified_chunks, query, context)

        return unified_chunks

    async def _extract_symbols_from_chunks(
        self, chunks: list[dict[str, Any]]
    ) -> list[str]:
        """Extract symbols from already-parsed chunks (language-agnostic).

        Leverages existing chunk data from UniversalParser which already extracted
        symbols for all 25+ supported languages. No re-parsing needed!

        Args:
            chunks: List of chunks from semantic search

        Returns:
            Deduplicated list of symbol names
        """
        symbols = set()

        for chunk in chunks:
            # Primary: Extract symbol name (function/class/method name)
            # This field is populated by UniversalParser for all languages
            if symbol := chunk.get("symbol"):
                if symbol and symbol.strip():
                    symbols.add(symbol.strip())

            # Secondary: Extract parameters as potential searchable symbols
            # Many functions/methods have meaningful parameter names
            metadata = chunk.get("metadata", {})
            if params := metadata.get("parameters"):
                if isinstance(params, list):
                    symbols.update(p.strip() for p in params if p and p.strip())

            # Tertiary: Extract from chunk_type-specific metadata
            # Some chunks have additional symbol information
            if chunk_type := metadata.get("kind"):
                # Skip generic types, focus on specific symbols
                if chunk_type not in ("block", "comment", "unknown"):
                    if name := chunk.get("name"):
                        symbols.add(name.strip())

        # Filter out common noise (single chars, numbers, common keywords)
        filtered_symbols = [
            s
            for s in symbols
            if len(s) > 1
            and not s.isdigit()
            and s.lower() not in {"self", "cls", "this"}
        ]

        logger.debug(
            f"Extracted {len(filtered_symbols)} symbols from {len(chunks)} chunks"
        )
        return filtered_symbols

    async def _rerank_symbols(
        self, symbols: list[str], query: str, context: ResearchContext
    ) -> list[str]:
        """Rerank symbols by relevance to query + BFS context (Step 4).

        Args:
            symbols: List of extracted symbol names
            query: Current query
            context: Research context with root query and ancestors

        Returns:
            Top N most relevant symbols (up to MAX_SYMBOLS_TO_SEARCH)
        """
        if not symbols:
            return []

        # If we have few symbols, return all
        if len(symbols) <= MAX_SYMBOLS_TO_SEARCH:
            return symbols[:MAX_SYMBOLS_TO_SEARCH]

        # Check if embedding provider supports reranking
        embedding_provider = self._embedding_manager.get_provider()
        if not (
            hasattr(embedding_provider, "supports_reranking")
            and embedding_provider.supports_reranking()
            and hasattr(embedding_provider, "rerank")
        ):
            logger.warning(
                "Embedding provider doesn't support reranking, returning first N symbols"
            )
            return symbols[:MAX_SYMBOLS_TO_SEARCH]

        try:
            # Combine query with BFS context for reranking (include full BFS path per algorithm)
            ancestors_path = " -> ".join(context.ancestors) if context.ancestors else ""
            search_context = f"{context.root_query} {ancestors_path} {query}".strip()

            # Rerank symbols against query context
            rerank_results = await embedding_provider.rerank(
                query=search_context, documents=symbols, top_k=min(10, len(symbols))
            )

            # Filter by RELEVANCE_THRESHOLD and return top MAX_SYMBOLS_TO_SEARCH
            top_symbols = [
                symbols[r.index]
                for r in rerank_results
                if r.score >= RELEVANCE_THRESHOLD
            ][:MAX_SYMBOLS_TO_SEARCH]

            if not top_symbols:
                # If filtering removed everything, take top N by score regardless
                top_symbols = [
                    symbols[r.index] for r in rerank_results[:MAX_SYMBOLS_TO_SEARCH]
                ]

            logger.debug(
                f"Reranked {len(symbols)} symbols -> {len(top_symbols)} top symbols"
            )
            return top_symbols

        except Exception as e:
            logger.warning(f"Symbol reranking failed: {e}, returning first N symbols")
            return symbols[:MAX_SYMBOLS_TO_SEARCH]

    async def _search_by_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Search codebase for top-ranked symbols using parallel async regex (Step 5).

        Uses async execution to avoid blocking the event loop, enabling better
        concurrency when searching for multiple symbols in parallel.

        Args:
            symbols: List of symbol names to search for

        Returns:
            List of chunks found via regex search
        """
        if not symbols:
            return []

        import re

        search_service = self._db_services.search_service

        async def search_symbol(symbol: str) -> list[dict[str, Any]]:
            """Search for a single symbol asynchronously."""
            try:
                # Escape special regex characters
                escaped = re.escape(symbol)
                # Match word boundaries to avoid partial matches
                # This works across all languages (identifier boundaries)
                pattern = rf"\b{escaped}\b"

                results, _ = await search_service.search_regex_async(
                    pattern=pattern,
                    page_size=10,  # Limit per symbol to avoid overwhelming results
                    offset=0,
                )

                logger.debug(f"Found {len(results)} chunks for symbol '{symbol}'")
                return results

            except Exception as e:
                logger.warning(f"Regex search failed for symbol '{symbol}': {e}")
                return []

        # Run all symbol searches concurrently
        results_per_symbol = await asyncio.gather(*[search_symbol(s) for s in symbols])

        # Flatten results
        all_results = []
        for results in results_per_symbol:
            all_results.extend(results)

        logger.debug(
            f"Parallel symbol regex search complete: {len(all_results)} total chunks from {len(symbols)} symbols"
        )
        return all_results

    async def _rerank_unified_chunks(
        self, chunks: list[dict[str, Any]], query: str, context: ResearchContext
    ) -> list[dict[str, Any]]:
        """Final reranking pass on unified semantic + regex results (Step 7).

        Args:
            chunks: Unified list of chunks from semantic and regex search
            query: Current query to rank against
            context: Research context with root query and BFS path

        Returns:
            Chunks sorted by relevance score (highest first)
        """
        if not chunks or len(chunks) <= 1:
            return chunks

        # Check if embedding provider supports reranking
        embedding_provider = self._embedding_manager.get_provider()
        if not (
            hasattr(embedding_provider, "supports_reranking")
            and embedding_provider.supports_reranking()
            and hasattr(embedding_provider, "rerank")
        ):
            logger.warning(
                "Embedding provider doesn't support reranking, skipping final rerank"
            )
            return chunks

        try:
            # Prepare documents for reranking (use content field)
            documents = [
                chunk.get("content", chunk.get("code", "")) for chunk in chunks
            ]

            # Build reranking query with full BFS context (per algorithm spec)
            ancestors_path = " -> ".join(context.ancestors) if context.ancestors else ""
            rerank_query = f"{context.root_query} {ancestors_path} {query}".strip()

            # Rerank all chunks against query with context
            rerank_results = await embedding_provider.rerank(
                query=rerank_query, documents=documents, top_k=len(documents)
            )

            # Update chunks with relevance scores
            for rerank_result in rerank_results:
                if 0 <= rerank_result.index < len(chunks):
                    chunks[rerank_result.index]["relevance_score"] = rerank_result.score

            # Sort by relevance score (highest first)
            sorted_chunks = sorted(
                chunks, key=lambda x: x.get("relevance_score", 0.0), reverse=True
            )

            logger.debug(
                f"Reranked {len(sorted_chunks)} unified chunks, top score: {sorted_chunks[0].get('relevance_score', 0.0):.3f}"
            )
            return sorted_chunks

        except Exception as e:
            logger.warning(
                f"Final chunk reranking failed: {e}, returning original order"
            )
            return chunks

    def _expand_to_natural_boundaries(
        self,
        lines: list[str],
        start_line: int,
        end_line: int,
        chunk: dict[str, Any],
        file_path: str,
    ) -> tuple[int, int]:
        """Expand chunk boundaries to complete function/class definitions.

        Uses existing chunk metadata (symbol, kind) and language-specific heuristics
        to detect natural code boundaries instead of using fixed 50-line windows.

        Args:
            lines: File content split by lines
            start_line: Original chunk start line (1-indexed)
            end_line: Original chunk end line (1-indexed)
            chunk: Chunk metadata with symbol, kind fields
            file_path: File path for language detection

        Returns:
            Tuple of (expanded_start_line, expanded_end_line) in 1-indexed format
        """
        if not ENABLE_SMART_BOUNDARIES:
            # Fallback to legacy fixed-window behavior
            context_lines = EXTRA_CONTEXT_TOKENS // 20  # ~50 lines
            start_idx = max(1, start_line - context_lines)
            end_idx = min(len(lines), end_line + context_lines)
            return start_idx, end_idx

        # Check if chunk metadata indicates this is already a complete unit
        metadata = chunk.get("metadata", {})
        chunk_kind = metadata.get("kind") or chunk.get("symbol_type", "")

        # If this chunk is marked as a complete function/class/method, use its exact boundaries
        if chunk_kind in ("function", "method", "class", "interface", "struct", "enum"):
            # Chunk is already a complete unit - just add small padding for context
            padding = 3  # A few lines for docstrings/decorators/comments
            start_idx = max(1, start_line - padding)
            end_idx = min(len(lines), end_line + padding)
            logger.debug(
                f"Using complete {chunk_kind} boundaries: {file_path}:{start_idx}-{end_idx}"
            )
            return start_idx, end_idx

        # For non-complete chunks, expand to natural boundaries
        # Detect language from file extension for language-specific logic
        file_path_lower = file_path.lower()
        is_python = file_path_lower.endswith((".py", ".pyw"))
        is_brace_lang = file_path_lower.endswith(
            (
                ".c",
                ".cpp",
                ".cc",
                ".cxx",
                ".h",
                ".hpp",
                ".rs",
                ".go",
                ".java",
                ".js",
                ".ts",
                ".tsx",
                ".jsx",
                ".cs",
                ".swift",
                ".kt",
                ".scala",
            )
        )

        # Convert to 0-indexed for array access
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines) - 1, end_line - 1)

        # Expand backward to find function/class start
        expanded_start = start_idx
        if is_python:
            # Look for def/class keywords at start of line with proper indentation
            for i in range(start_idx - 1, max(0, start_idx - 200), -1):
                line = lines[i].strip()
                if line.startswith(("def ", "class ", "async def ")):
                    expanded_start = i
                    break
                # Stop at empty lines followed by significant dedents (module boundary)
                if not line and i > 0:
                    next_line = lines[i + 1].lstrip() if i + 1 < len(lines) else ""
                    if next_line and not next_line.startswith((" ", "\t")):
                        break
        elif is_brace_lang:
            # Look for opening braces and function signatures
            brace_depth = 0
            for i in range(start_idx, max(0, start_idx - 200), -1):
                line = lines[i]
                # Count braces
                open_braces = line.count("{")
                close_braces = line.count("}")
                brace_depth += close_braces - open_braces

                # Found matching opening brace
                if brace_depth > 0 and "{" in line:
                    # Look backward for function signature
                    for j in range(i, max(0, i - 10), -1):
                        sig_line = lines[j].strip()
                        # Heuristic: function signatures often have (...) or start with keywords
                        if "(" in sig_line and (")" in sig_line or j < i):
                            expanded_start = j
                            break
                    if expanded_start != start_idx:
                        break

        # Expand forward to find function/class end
        expanded_end = end_idx
        if is_python:
            # Find end by detecting dedentation back to original level
            if expanded_start < len(lines):
                start_indent = len(lines[expanded_start]) - len(
                    lines[expanded_start].lstrip()
                )
                for i in range(end_idx + 1, min(len(lines), end_idx + 200)):
                    line = lines[i]
                    if line.strip():  # Non-empty line
                        line_indent = len(line) - len(line.lstrip())
                        # Dedented to same or less indentation = end of block
                        if line_indent <= start_indent:
                            expanded_end = i - 1
                            break
                else:
                    # Reached search limit, use current position
                    expanded_end = min(len(lines) - 1, end_idx + 50)
        elif is_brace_lang:
            # Find matching closing brace
            brace_depth = 0
            for i in range(expanded_start, min(len(lines), end_idx + 200)):
                line = lines[i]
                open_braces = line.count("{")
                close_braces = line.count("}")
                brace_depth += open_braces - close_braces

                # Found matching closing brace
                if brace_depth == 0 and i > expanded_start and "}" in line:
                    expanded_end = i
                    break

        # Safety: Don't expand beyond max limit
        if expanded_end - expanded_start > MAX_BOUNDARY_EXPANSION_LINES:
            logger.debug(
                f"Boundary expansion too large ({expanded_end - expanded_start} lines), "
                f"limiting to {MAX_BOUNDARY_EXPANSION_LINES}"
            )
            expanded_end = expanded_start + MAX_BOUNDARY_EXPANSION_LINES

        # Convert back to 1-indexed
        final_start = expanded_start + 1
        final_end = expanded_end + 1

        logger.debug(
            f"Expanded boundaries: {file_path}:{start_line}-{end_line} -> "
            f"{final_start}-{final_end} ({final_end - final_start} lines)"
        )

        return final_start, final_end

    async def _read_files_with_budget(
        self, chunks: list[dict[str, Any]], max_tokens: int | None = None
    ) -> dict[str, str]:
        """Read files containing chunks within token budget (Step 8).

        Per algorithm: Limit overall data to adaptive budget (or legacy MAX_FILE_CONTENT_TOKENS).

        Args:
            chunks: List of chunks
            max_tokens: Maximum tokens for file contents (uses adaptive budget if provided)

        Returns:
            Dictionary mapping file paths to contents (limited to budget)
        """
        # Group chunks by file
        files_to_chunks: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks:
            file_path = chunk.get("file_path") or chunk.get("path", "")
            if file_path:
                if file_path not in files_to_chunks:
                    files_to_chunks[file_path] = []
                files_to_chunks[file_path].append(chunk)

        # Use adaptive budget or fall back to legacy constant
        budget_limit = max_tokens if max_tokens is not None else MAX_FILE_CONTENT_TOKENS

        # Read files with budget (track total tokens per algorithm spec)
        file_contents: dict[str, str] = {}
        total_tokens = 0
        llm = self._llm_manager.get_utility_provider()

        # Get base directory for path resolution
        base_dir = self._db_services.provider.get_base_directory()

        for file_path, file_chunks in files_to_chunks.items():
            # Check if we've hit the overall token limit
            if total_tokens >= budget_limit:
                logger.debug(
                    f"Reached token limit ({budget_limit:,}), stopping file reading"
                )
                break

            try:
                # Resolve path relative to base directory
                if Path(file_path).is_absolute():
                    path = Path(file_path)
                else:
                    path = base_dir / file_path

                if not path.exists():
                    logger.warning(f"File not found (expected at {path}): {file_path}")
                    continue

                # Calculate token budget for this file
                num_chunks = len(file_chunks)
                budget = TOKEN_BUDGET_PER_FILE * num_chunks

                # Read file
                content = path.read_text(encoding="utf-8", errors="ignore")

                # Estimate tokens
                estimated_tokens = llm.estimate_tokens(content)

                if estimated_tokens <= budget:
                    # File fits in budget, check against overall limit
                    if total_tokens + estimated_tokens <= budget_limit:
                        file_contents[file_path] = content
                        total_tokens += estimated_tokens
                    else:
                        # Truncate to fit within overall limit
                        remaining_tokens = budget_limit - total_tokens
                        if remaining_tokens > 500:  # Only include if meaningful
                            chars_to_include = remaining_tokens * 4
                            file_contents[file_path] = content[:chars_to_include]
                            total_tokens = budget_limit
                        break
                else:
                    # File too large, extract chunks with smart boundary detection
                    chunk_contents = []
                    lines = content.split("\n")  # Pre-split for all chunks in this file

                    for chunk in file_chunks:
                        start_line = chunk.get("start_line", 1)
                        end_line = chunk.get("end_line", 1)

                        # Use smart boundary detection to expand to complete functions/classes
                        expanded_start, expanded_end = self._expand_to_natural_boundaries(
                            lines, start_line, end_line, chunk, file_path
                        )

                        # Store expanded range in chunk for later deduplication
                        chunk["expanded_start_line"] = expanded_start
                        chunk["expanded_end_line"] = expanded_end

                        # Extract chunk with smart boundaries (convert 1-indexed to 0-indexed)
                        start_idx = max(0, expanded_start - 1)
                        end_idx = min(len(lines), expanded_end)

                        chunk_with_context = "\n".join(lines[start_idx:end_idx])
                        chunk_contents.append(chunk_with_context)

                    combined_chunks = "\n\n...\n\n".join(chunk_contents)
                    chunk_tokens = llm.estimate_tokens(combined_chunks)

                    # Check against overall token limit
                    if total_tokens + chunk_tokens <= budget_limit:
                        file_contents[file_path] = combined_chunks
                        total_tokens += chunk_tokens
                    else:
                        # Truncate to fit
                        remaining_tokens = budget_limit - total_tokens
                        if remaining_tokens > 500:
                            chars_to_include = remaining_tokens * 4
                            file_contents[file_path] = combined_chunks[:chars_to_include]
                            total_tokens = budget_limit
                        break

            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                continue

        # Validate that at least some files were loaded if chunks were provided
        if chunks and not file_contents:
            raise RuntimeError(
                f"Failed to load ANY files from {len(files_to_chunks)} unique paths. "
                f"Check base_directory configuration and file paths in database. "
                f"Base directory: {base_dir}"
            )

        logger.debug(
            f"File reading complete: Loaded {len(file_contents)} files with {total_tokens:,} tokens "
            f"(limit: {budget_limit:,})"
        )
        return file_contents

    def _is_file_fully_read(self, file_content: str) -> bool:
        """Detect if file_content is full file vs partial chunks.

        Heuristic: Partial reads have "..." separator between chunks.

        Args:
            file_content: Content from file_contents dict

        Returns:
            True if full file was read, False if partial chunks
        """
        return "\n\n...\n\n" not in file_content

    def _get_chunk_expanded_range(self, chunk: dict[str, Any]) -> tuple[int, int]:
        """Get expanded line range for chunk.

        If expansion already computed and stored in chunk, return it.
        Otherwise, re-compute using _expand_to_natural_boundaries().

        Args:
            chunk: Chunk dictionary with metadata

        Returns:
            Tuple of (expanded_start_line, expanded_end_line) in 1-indexed format
        """
        # Check if already stored (after enhancement in _read_files_with_budget)
        if "expanded_start_line" in chunk and "expanded_end_line" in chunk:
            return (chunk["expanded_start_line"], chunk["expanded_end_line"])

        # Re-compute (fallback)
        file_path = chunk.get("file_path")
        start_line = chunk.get("start_line", 0)
        end_line = chunk.get("end_line", 0)

        if not file_path or not start_line or not end_line:
            return (start_line, end_line)

        # Read file lines
        try:
            base_dir = self._db_services.provider.get_base_directory()
            if Path(file_path).is_absolute():
                path = Path(file_path)
            else:
                path = base_dir / file_path

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            logger.debug(f"Could not re-read file for expansion: {file_path}: {e}")
            return (start_line, end_line)

        expanded_start, expanded_end = self._expand_to_natural_boundaries(
            lines, start_line, end_line, chunk, file_path
        )

        return (expanded_start, expanded_end)

    def _collect_ancestor_data(self, node: BFSNode) -> dict[str, Any]:
        """Traverse parent chain and collect all ancestor chunks/files.

        Args:
            node: Current BFS node

        Returns:
            Dictionary with:
                - files_fully_read: set[str] - Paths of fully-read files
                - chunk_ranges: dict[str, list[tuple[int, int]]] - file → [(start, end)]
        """
        files_fully_read: set[str] = set()
        chunk_ranges: dict[str, list[tuple[int, int]]] = {}

        current = node.parent
        while current:
            # Check which files were fully read
            for file_path, content in current.file_contents.items():
                if self._is_file_fully_read(content):
                    files_fully_read.add(file_path)

            # Collect expanded chunk ranges
            for chunk in current.chunks:
                file_path = chunk.get("file_path")
                if file_path:
                    expanded_range = self._get_chunk_expanded_range(chunk)
                    chunk_ranges.setdefault(file_path, []).append(expanded_range)

            current = current.parent

        return {
            "files_fully_read": files_fully_read,
            "chunk_ranges": chunk_ranges,
        }

    def _is_chunk_duplicate(
        self,
        chunk: dict[str, Any],
        chunk_expanded_range: tuple[int, int],
        ancestor_data: dict[str, Any],
    ) -> bool:
        """Check if chunk is 100% duplicate of ancestor's data.

        Returns True only if:
        1. Chunk's file was fully read by ancestor, OR
        2. Chunk's expanded range is 100% contained in ancestor's expanded chunk

        Partial overlaps return False (counted as new information).

        Args:
            chunk: Chunk dictionary
            chunk_expanded_range: Expanded range for this chunk
            ancestor_data: Data from _collect_ancestor_data

        Returns:
            True if chunk is 100% duplicate, False otherwise
        """
        file_path = chunk.get("file_path")
        if not file_path:
            return False

        expanded_start, expanded_end = chunk_expanded_range

        # Check 1: File fully read by ancestor
        if file_path in ancestor_data["files_fully_read"]:
            return True

        # Check 2: 100% containment in ancestor's expanded chunks
        for anc_start, anc_end in ancestor_data["chunk_ranges"].get(file_path, []):
            # Must be completely contained (100% overlap)
            if expanded_start >= anc_start and expanded_end <= anc_end:
                return True

        return False

    def _detect_new_information(
        self,
        node: BFSNode,
        chunks: list[dict[str, Any]],
    ) -> tuple[bool, dict[str, Any]]:
        """Detect if node has new information vs ancestors.

        Args:
            node: Current BFS node
            chunks: Chunks found for this node

        Returns:
            Tuple of (has_new_info, stats):
                - has_new_info: Boolean indicating if node has truly new chunks
                - stats: Dict with breakdown of new/duplicate counts
        """
        if not node.parent:
            # Root node always has new info
            return (True, {"new_chunks": len(chunks), "duplicate_chunks": 0, "total_chunks": len(chunks)})

        if not chunks:
            # No chunks at all
            return (False, {"new_chunks": 0, "duplicate_chunks": 0, "total_chunks": 0})

        # Collect ancestor data
        ancestor_data = self._collect_ancestor_data(node)

        # Check each chunk
        new_count = 0
        duplicate_count = 0

        for chunk in chunks:
            # Get expanded range (from stored data or re-compute)
            expanded_range = self._get_chunk_expanded_range(chunk)

            is_duplicate = self._is_chunk_duplicate(chunk, expanded_range, ancestor_data)

            if is_duplicate:
                duplicate_count += 1
            else:
                new_count += 1

        has_new_info = new_count > 0

        stats = {
            "new_chunks": new_count,
            "duplicate_chunks": duplicate_count,
            "total_chunks": len(chunks),
        }

        return (has_new_info, stats)

    async def _generate_follow_up_questions(
        self,
        query: str,
        context: ResearchContext,
        file_contents: dict[str, str],
        chunks: list[dict[str, Any]],
        max_input_tokens: int | None = None,
    ) -> list[str]:
        """Generate follow-up questions using LLM.

        Args:
            query: Current query
            context: Research context
            file_contents: File contents found
            chunks: Chunks found
            max_input_tokens: Maximum tokens for LLM input (uses adaptive budget if provided)

        Returns:
            List of follow-up questions
        """
        # Validate that file contents were provided (required by algorithm)
        if not file_contents:
            logger.error(
                "Cannot generate follow-up questions: no file contents provided. "
                f"Query: {query}, Chunks: {len(chunks)}"
            )
            return []  # Return empty list instead of invalid questions

        llm = self._llm_manager.get_utility_provider()

        # Build prompt
        system = """You are a research assistant helping explore a codebase.
Your task is to generate focused follow-up questions to deepen architectural understanding.

Generate 1-3 follow-up questions that would:
1. Clarify how components interact (if current code shows isolated components)
2. Trace data/control flow (if flow is unclear)
3. Understand dependencies (if related components are referenced but not found)

RULES:
- Questions must be DIRECTLY about code elements found (functions, classes, imports mentioned)
- Prioritize architectural understanding over implementation details
- Each question must be specific and searchable (include exact symbol/file names when possible)
- NO generic questions like "how does X work in general"
- If code fully answers the question, generate 0-1 follow-ups (not 3)

FORMAT: Numbered list, one question per line"""

        # Build code context from file contents
        # Note: files already limited by _read_files_with_budget
        # This applies the total LLM input budget (query + ancestors + files)
        code_context = []
        total_tokens = 0
        max_tokens_for_context = (
            max_input_tokens if max_input_tokens is not None else MAX_LLM_INPUT_TOKENS
        )

        for path, content in file_contents.items():
            content_tokens = llm.estimate_tokens(content)
            if total_tokens + content_tokens <= max_tokens_for_context:
                code_context.append(f"File: {path}\n{'=' * 60}\n{content}\n{'=' * 60}")
                total_tokens += content_tokens
            else:
                # Truncate to fit within total budget
                remaining_tokens = max_tokens_for_context - total_tokens
                if remaining_tokens > 500:  # Only include if meaningful
                    chars_to_include = remaining_tokens * 4  # ~4 chars per token
                    code_context.append(
                        f"File: {path}\n{'=' * 60}\n{content[:chars_to_include]}...\n{'=' * 60}"
                    )
                break

        logger.debug(
            f"LLM input: {total_tokens} tokens from {len(code_context)} files (budget: {max_tokens_for_context})"
        )

        code_section = (
            "\n\n".join(code_context) if code_context else "No code files loaded"
        )

        # Also include chunk snippets for context
        chunks_preview = "\n".join(
            [
                f"- {chunk.get('file_path', 'unknown')}:{chunk.get('start_line', '?')}-{chunk.get('end_line', '?')} ({chunk.get('symbol', 'no symbol')})"
                for chunk in chunks[:10]
            ]
        )

        prompt = f"""Root Query: {context.root_query}

Current Question: {query}

BFS Context: {" -> ".join(context.ancestors)}

Code Found:
{code_section}

Chunks Overview:
{chunks_preview}

Generate focused follow-up questions to deepen architectural understanding of the ROOT query.
Each question should be about specific code elements found (functions, classes, files mentioned above).

Maximum {MAX_FOLLOWUP_QUESTIONS} questions. If the code fully answers the question, generate fewer."""

        response = await llm.complete(prompt, system=system, max_completion_tokens=3000)

        # Parse questions from response
        questions = []
        for line in response.content.split("\n"):
            line = line.strip()
            # Match numbered list items
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove number/bullet and extract question
                question = line.lstrip("0123456789.-) ").strip()
                if question:
                    questions.append(question)

        # Filter questions by relevance to root query
        if questions:
            questions = await self._filter_relevant_followups(
                questions, context.root_query, query, context
            )

        return questions[:MAX_FOLLOWUP_QUESTIONS]

    async def _synthesize_questions(
        self, nodes: list[BFSNode], context: ResearchContext, target_count: int
    ) -> list[BFSNode]:
        """Synthesize N new questions capturing unexplored aspects of input questions.

        Purpose: When BFS level has too many questions, synthesize them into
        fewer high-level questions that explore NEW areas for comprehensive coverage.

        Args:
            nodes: List of BFS nodes to synthesize
            context: Research context
            target_count: Target number of synthesized questions

        Returns:
            Fresh BFSNode objects with synthesized queries and empty metadata.
            These nodes will find their own chunks during processing.
        """
        if len(nodes) <= target_count:
            return nodes

        llm = self._llm_manager.get_utility_provider()

        # Extract questions from all nodes
        questions_str = "\n".join(
            [f"{i + 1}. {node.query}" for i, node in enumerate(nodes)]
        )

        # Create synthetic merge parent
        merge_parent = BFSNode(
            query=f"[Merge of {len(nodes)} research directions]",
            depth=nodes[0].depth - 1,
            node_id=self._get_next_node_id(),
            children=nodes,  # Reference all input nodes
        )

        system = """You are a research assistant synthesizing research directions.
Your task is to create NEW questions that explore UNEXPLORED aspects to complete the research picture."""

        prompt = f"""Root Query: {context.root_query}

Current research directions being merged:
{questions_str}

Synthesize {target_count} questions that:
1. Explore NEW, UNEXPLORED aspects to complete the full picture
2. Integrate multiple perspectives into coherent questions
3. Are distinct from existing research paths
4. Uncover missing architectural pieces
5. Are concrete and searchable (include specific code elements when possible)

OUTPUT FORMAT (numbered list):
1. [synthesized question 1]
2. [synthesized question 2]
3. [synthesized question 3]

Generate {target_count} synthesized questions:"""

        try:
            response = await llm.complete(prompt, system=system, max_completion_tokens=2000)

            # Parse synthesized questions
            synthesized_queries = []
            for line in response.content.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    question = line.lstrip("0123456789.-) ").strip()
                    if question:
                        synthesized_queries.append(question)

            if not synthesized_queries:
                logger.warning("Synthesis returned no questions, falling back to first N nodes")
                return nodes[:target_count]

            # Create fresh BFSNode objects with empty metadata
            synthesized_nodes = []
            for query in synthesized_queries[:target_count]:
                node = BFSNode(
                    query=query,
                    parent=merge_parent,  # Point to synthetic parent
                    depth=nodes[0].depth,  # Same depth as input nodes
                    node_id=self._get_next_node_id(),
                    chunks=[],  # Empty - will populate during processing
                    file_contents={},  # Empty - will populate during processing
                )
                synthesized_nodes.append(node)

            logger.info(
                f"Synthesized {len(nodes)} questions into {len(synthesized_nodes)} new research directions"
            )

            return synthesized_nodes

        except Exception as e:
            logger.warning(f"Question synthesis failed: {e}, falling back to first N nodes")
            return nodes[:target_count]

    def _aggregate_all_findings(self, root: BFSNode) -> dict[str, Any]:
        """Aggregate all chunks and files from entire BFS tree.

        Walks the complete BFS tree and collects all discovered chunks and files,
        deduplicating by chunk_id and file_path.

        Args:
            root: Root BFS node

        Returns:
            Dictionary with:
                - chunks: List of unique chunks (deduplicated by chunk_id)
                - files: Dict mapping file_path to content (deduplicated)
                - stats: Statistics about aggregation
        """
        logger.info("Aggregating all findings from BFS tree")

        # Collect all nodes via BFS traversal
        all_nodes: list[BFSNode] = []
        queue = [root]
        while queue:
            node = queue.pop(0)
            all_nodes.append(node)
            queue.extend(node.children)

        # Aggregate chunks (deduplicate by chunk_id)
        chunks_map: dict[str, dict[str, Any]] = {}
        for node in all_nodes:
            for chunk in node.chunks:
                chunk_id = chunk.get("chunk_id") or chunk.get("id")
                if chunk_id and chunk_id not in chunks_map:
                    chunks_map[chunk_id] = chunk

        # Aggregate files (deduplicate by file_path)
        files_map: dict[str, str] = {}
        for node in all_nodes:
            for file_path, content in node.file_contents.items():
                if file_path not in files_map:
                    files_map[file_path] = content

        # Calculate statistics
        total_chunks_found = sum(len(node.chunks) for node in all_nodes)
        total_files_found = sum(len(node.file_contents) for node in all_nodes)

        stats = {
            "total_nodes": len(all_nodes),
            "unique_chunks": len(chunks_map),
            "unique_files": len(files_map),
            "total_chunks_found": total_chunks_found,
            "total_files_found": total_files_found,
            "deduplication_ratio_chunks": (
                f"{total_chunks_found / len(chunks_map):.2f}x"
                if chunks_map
                else "N/A"
            ),
            "deduplication_ratio_files": (
                f"{total_files_found / len(files_map):.2f}x"
                if files_map
                else "N/A"
            ),
        }

        logger.info(
            f"Aggregation complete: {stats['unique_chunks']} unique chunks, "
            f"{stats['unique_files']} unique files from {stats['total_nodes']} nodes"
        )

        return {
            "chunks": list(chunks_map.values()),
            "files": files_map,
            "stats": stats,
        }

    def _manage_token_budget_for_synthesis(
        self, chunks: list[dict[str, Any]], files: dict[str, str]
    ) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
        """Manage token budget to fit within SINGLE_PASS_MAX_TOKENS limit.

        Prioritizes files by chunk relevance scores. If total exceeds budget,
        includes full files for high-priority items and snippets for lower-priority.

        Args:
            chunks: All chunks from BFS traversal
            files: All file contents from BFS traversal

        Returns:
            Tuple of (prioritized_chunks, budgeted_files, budget_info)
        """
        llm = self._llm_manager.get_utility_provider()

        # Calculate available tokens for code content
        # Total budget - output budget - overhead = input budget
        available_tokens = (
            SINGLE_PASS_MAX_TOKENS
            - SINGLE_PASS_OUTPUT_TOKENS
            - SINGLE_PASS_OVERHEAD_TOKENS
        )

        logger.info(
            f"Managing token budget: {available_tokens:,} tokens available for code content"
        )

        # Sort chunks by relevance score (highest first)
        sorted_chunks = sorted(
            chunks, key=lambda c: c.get("relevance_score", 0.0), reverse=True
        )

        # Build file priority map based on chunk relevance
        file_priorities: dict[str, float] = {}
        file_to_chunks: dict[str, list[dict[str, Any]]] = {}

        for chunk in sorted_chunks:
            file_path = chunk.get("file_path", "")
            if file_path:
                if file_path not in file_priorities:
                    file_priorities[file_path] = 0.0
                    file_to_chunks[file_path] = []

                # Accumulate relevance scores for this file
                file_priorities[file_path] += chunk.get("relevance_score", 0.0)
                file_to_chunks[file_path].append(chunk)

        # Sort files by priority
        sorted_files = sorted(
            file_priorities.items(), key=lambda x: x[1], reverse=True
        )

        # Build budgeted file contents
        budgeted_files: dict[str, str] = {}
        total_tokens = 0
        files_included_fully = 0
        files_included_partial = 0
        files_excluded = 0

        for file_path, priority in sorted_files:
            if file_path not in files:
                continue

            content = files[file_path]
            content_tokens = llm.estimate_tokens(content)

            if total_tokens + content_tokens <= available_tokens:
                # Include full file
                budgeted_files[file_path] = content
                total_tokens += content_tokens
                files_included_fully += 1
            else:
                # Check if we can include a snippet
                remaining_tokens = available_tokens - total_tokens

                if remaining_tokens > 1000:  # Only include if meaningful
                    # Include top chunks from this file as snippets
                    file_chunks = file_to_chunks[file_path]
                    snippet_parts = []

                    for chunk in file_chunks[:5]:  # Top 5 chunks max
                        start_line = chunk.get("start_line", 1)
                        end_line = chunk.get("end_line", 1)
                        chunk_content = chunk.get("content", "")

                        snippet_parts.append(
                            f"# Lines {start_line}-{end_line}\n{chunk_content}"
                        )

                    snippet = "\n\n".join(snippet_parts)
                    snippet_tokens = llm.estimate_tokens(snippet)

                    if snippet_tokens <= remaining_tokens:
                        budgeted_files[file_path] = snippet
                        total_tokens += snippet_tokens
                        files_included_partial += 1
                    else:
                        # Truncate snippet to fit
                        chars_to_include = remaining_tokens * 4  # ~4 chars per token
                        budgeted_files[file_path] = snippet[:chars_to_include]
                        total_tokens = available_tokens
                        files_included_partial += 1
                        break  # Budget exhausted
                else:
                    files_excluded += 1
                    break  # Budget exhausted

        budget_info = {
            "available_tokens": available_tokens,
            "used_tokens": total_tokens,
            "utilization": f"{(total_tokens / available_tokens) * 100:.1f}%",
            "files_included_fully": files_included_fully,
            "files_included_partial": files_included_partial,
            "files_excluded": files_excluded,
            "total_files": len(sorted_files),
        }

        logger.info(
            f"Token budget managed: {total_tokens:,}/{available_tokens:,} tokens used ({budget_info['utilization']}), "
            f"{files_included_fully} full files, {files_included_partial} partial, {files_excluded} excluded"
        )

        return sorted_chunks, budgeted_files, budget_info

    async def _single_pass_synthesis(
        self,
        root_query: str,
        chunks: list[dict[str, Any]],
        files: dict[str, str],
        context: ResearchContext,
    ) -> str:
        """Perform single-pass synthesis with all aggregated data.

        Uses modern LLM large context windows to synthesize answer from complete
        data in one pass, avoiding information loss from progressive compression.

        Args:
            root_query: Original research query
            chunks: Prioritized chunks from BFS traversal
            files: Budgeted file contents
            context: Research context

        Returns:
            Synthesized answer from single LLM call
        """
        logger.info(f"Starting single-pass synthesis with {len(files)} files, {len(chunks)} chunks")

        llm = self._llm_manager.get_synthesis_provider()

        # Build code context sections
        code_sections = []

        # Group chunks by file for better presentation
        chunks_by_file: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks:
            file_path = chunk.get("file_path", "unknown")
            if file_path not in chunks_by_file:
                chunks_by_file[file_path] = []
            chunks_by_file[file_path].append(chunk)

        # Build sections from files (already budgeted)
        for file_path, content in files.items():
            # Get line ranges for this file's chunks if available
            if file_path in chunks_by_file:
                file_chunks = chunks_by_file[file_path]
                start_line = min(c.get("start_line", 1) for c in file_chunks)
                end_line = max(c.get("end_line", 1) for c in file_chunks)
                line_range = f":{start_line}-{end_line}"
            else:
                line_range = ""

            code_sections.append(
                f"### {file_path}{line_range}\n"
                f"{'=' * 80}\n"
                f"{content}\n"
                f"{'=' * 80}"
            )

        code_context = "\n\n".join(code_sections)

        # Build comprehensive synthesis prompt (adapted from Code Expert methodology)
        system = f"""You are an expert code researcher with deep experience across all software domains. Your mission is comprehensive code analysis - synthesizing the complete codebase picture to answer the research question with full architectural understanding.

**Context:**
You have access to the COMPLETE set of code discovered during BFS exploration. This is not a discovery phase - all relevant code has been found and is provided to you. Your task is to synthesize this complete picture into a comprehensive answer.

**Target Output:** {SINGLE_PASS_OUTPUT_TOKENS:,} tokens of comprehensive, factual analysis.

**Analysis Methodology:**

1. **Structure & Organization**
   Map the directory layout and module organization. Identify component responsibilities and boundaries. Document key design decisions observed in the code. Explain the "why" behind the organization when evident from the code.

2. **Component Analysis**
   For each relevant component:
   - **Purpose**: What it does and why (based on code, not speculation)
   - **Location**: Files and directories with line numbers
   - **Key Elements**: Classes/functions with signatures (file:line refs)
   - **Dependencies**: What it uses and what uses it
   - **Patterns**: Design patterns and conventions observed
   - **Critical Sections**: Important logic with specific citations

3. **Data & Control Flow**
   Trace how data moves through relevant components. Document execution paths and state management. Include concrete values: buffer sizes, timeouts, limits, thresholds. Show transformations with actual data types. Map async/sync boundaries and concurrency patterns.

4. **Patterns & Conventions**
   Identify consistent patterns across the codebase. Document coding standards observed. Recognize architectural decisions and trade-offs. Find reusable components and utilities. Note error handling and edge case strategies.

5. **Integration Points**
   Document APIs, external systems, and configurations. Show how components collaborate with exact method signatures. Include parameter types, return values, and data formats. Map coordination mechanisms and shared resources.

**Output Format:**
```
## Overview
[Direct answer to the query with system purpose and design approach]

## Structure & Organization
[Directory layout, module organization, key design decisions observed]

## Component Analysis
[For each major component:]

**[Component Name]**
- **Purpose**: [What it does and why]
- **Location**: [Files with line numbers]
- **Key Elements**: [Classes/functions with file:line refs]
- **Dependencies**: [What it uses/what uses it]
- **Patterns**: [Design patterns observed]
- **Critical Sections**: [Important logic with citations]

## Data & Control Flow
[How data moves through components, execution paths, state management]

## Patterns & Conventions
[Consistent patterns, coding standards, architectural decisions]

## Integration Points
[APIs, configurations, external systems, collaboration mechanisms]

## Key Findings
[Direct answers to the research question with evidence]
```

**Quality Principles:**
- Always provide specific file paths and line numbers (file.py:123 format)
- Explain the 'why' behind code organization when evident
- Extract exact values from code (never "several", "many", "various")
- Document HOW things work, not just that they exist
- Include actual error messages, log formats, constants with values
- State complexity (O() notation) and performance characteristics
- Focus on actionable insights for developers
- Connect all findings back to the research question
- Work only with provided code - no speculation beyond what code shows
- Every technical claim must have a citation

**Remember:**
- You have the COMPLETE picture - all relevant code is provided
- Leverage this complete view to provide thorough architectural understanding
- Answer the specific research question with full context
- Be direct and confident - state facts from the code
- Focus on what developers need to know to work with this codebase"""

        prompt = f"""Question: {root_query}

Complete Code Context:
{code_context}

Provide a comprehensive analysis that answers the question using ALL the code provided.
Focus on complete architectural understanding - you have the full picture."""

        logger.info(
            f"Calling LLM for single-pass synthesis "
            f"(max_completion_tokens={SINGLE_PASS_OUTPUT_TOKENS:,}, "
            f"timeout={SINGLE_PASS_TIMEOUT_SECONDS}s)"
        )

        response = await llm.complete(
            prompt,
            system=system,
            max_completion_tokens=SINGLE_PASS_OUTPUT_TOKENS,
            timeout=SINGLE_PASS_TIMEOUT_SECONDS,
        )

        answer = response.content

        logger.info(
            f"Single-pass synthesis complete: {llm.estimate_tokens(answer):,} tokens generated"
        )

        return answer

    def _filter_verbosity(self, text: str) -> str:
        """Remove common LLM verbosity patterns from synthesis output.

        Acts as safety net even with good prompts. Strips defensive caveats,
        meta-commentary, and unnecessary qualifications.

        Args:
            text: Synthesis text to filter

        Returns:
            Filtered text with verbose patterns removed
        """
        import re

        # Patterns to remove (from research on LLM verbosity)
        patterns_to_remove = [
            r"It'?s important to note that\s+",
            r"It'?s worth noting that\s+",
            r"It should be noted that\s+",
            r"However, it should be mentioned that\s+",
            r"Please note that\s+",
            r"As mentioned (?:earlier|above|previously),?\s+",
            # Remove standalone "No information found" lines from body (keep in "Missing:" context)
            r"^No information (?:was )?found (?:for|about)[^\n]+\n",
            r"^Unfortunately, the (?:code|analysis) does not (?:show|provide)[^\n]+\n",
            # Remove vague precision statements
            r"The (?:exact|precise|specific) (?:implementation|details?|mechanism|values?) (?:is|are) not (?:provided|documented|shown|clear|available) in the (?:code|analysis)[,.]?\s*",
            r"(?:More|Additional) (?:research|investigation|analysis|context) (?:is|would be) (?:needed|required)[,.]?\s*",
        ]

        filtered = text
        for pattern in patterns_to_remove:
            filtered = re.sub(pattern, "", filtered, flags=re.IGNORECASE | re.MULTILINE)

        # Remove excessive newlines left by removals (max 2 consecutive newlines)
        filtered = re.sub(r'\n{3,}', '\n\n', filtered)

        # Log if we actually filtered anything
        if filtered != text:
            chars_removed = len(text) - len(filtered)
            logger.debug(f"Verbosity filter removed {chars_removed} chars of meta-commentary")

        return filtered

    def _validate_output_quality(self, answer: str, target_tokens: int) -> tuple[str, list[str]]:
        """Validate output quality for conciseness and actionability.

        Args:
            answer: Synthesized answer to validate
            target_tokens: Target token count for this output

        Returns:
            Tuple of (validated_answer, list_of_warnings)
        """
        warnings = []
        llm = self._llm_manager.get_utility_provider()

        # Check 1: Detect theoretical placeholders
        theoretical_patterns = [
            "provide exact",
            "provide precise",
            "specify exact",
            "implementation-dependent",
            "precise line-level mappings",
            "exact numeric budgets",
            "provide the actual",
            "should specify",
            "need to determine",
            "requires clarification"
        ]

        for pattern in theoretical_patterns:
            if pattern.lower() in answer.lower():
                warnings.append(
                    f"QUALITY: Output contains theoretical placeholder: '{pattern}'. "
                    "This suggests lack of concrete information."
                )
                logger.warning(f"Output quality issue: contains '{pattern}'")

        # Check 2: Citation density (should have reasonable citations)
        import re
        citations = re.findall(r'[\w/]+\.\w+:\d+', answer)
        citation_count = len(citations)
        answer_tokens = llm.estimate_tokens(answer)

        if answer_tokens > 1000 and citation_count < 5:
            warnings.append(
                f"QUALITY: Low citation density ({citation_count} citations in {answer_tokens} tokens). "
                "Output may lack concrete code references."
            )
            logger.warning(f"Low citation density: {citation_count} citations in {answer_tokens} tokens")

        # Check 3: Excessive length
        if answer_tokens > target_tokens * 1.5:
            warnings.append(
                f"QUALITY: Output is verbose ({answer_tokens:,} tokens vs {target_tokens:,} target). "
                "May need tighter prompting."
            )
            logger.warning(f"Verbose output: {answer_tokens:,} tokens (target: {target_tokens:,})")

        # Check 4: Vague measurements (should use exact numbers)
        vague_patterns = [
            r'\b(several|many|few|some|various|multiple|numerous)\s+(seconds|minutes|items|entries|elements|chunks)',
            r'\b(around|approximately|roughly|about)\s+\d+',
            r'\bhundreds of\b',
            r'\bthousands of\b',
        ]

        for pattern in vague_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            if matches:
                warnings.append(
                    f"QUALITY: Vague measurement detected: {matches[0]}. "
                    "Should use exact values."
                )
                logger.warning(f"Vague measurement in output: {matches[0]}")
                break  # Only report first instance

        return answer, warnings

    def _validate_citations(self, answer: str, chunks: list[dict[str, Any]]) -> str:
        """Ensure answer contains file:line citations.

        Args:
            answer: Answer text to validate
            chunks: Chunks that were analyzed

        Returns:
            Answer with citations appended if missing
        """
        if not REQUIRE_CITATIONS:
            return answer

        import re

        # Check for citation pattern: filename.ext:123 or filename.ext:123-456
        citation_pattern = r'[\w/]+\.\w+:\d+(?:-\d+)?'
        citations = re.findall(citation_pattern, answer)

        if not citations and chunks:
            # Answer missing citations - warn and append key files
            logger.warning("LLM answer missing file:line citations")
            key_files = set()
            for chunk in chunks[:5]:  # Top 5 chunks
                file_path = chunk.get('file_path', '')
                line = chunk.get('start_line', '')
                if file_path and line:
                    key_files.add(f"{file_path}:{line}")

            if key_files:
                answer += "\n\n**Key files referenced:**\n"
                answer += "\n".join(f"- {f}" for f in sorted(key_files))

        return answer

    async def _filter_relevant_followups(
        self,
        questions: list[str],
        root_query: str,
        current_query: str,
        context: ResearchContext,
    ) -> list[str]:
        """Filter follow-ups by relevance to root query and architectural value.

        Args:
            questions: Candidate follow-up questions
            root_query: Original root query
            current_query: Current question being explored
            context: Research context

        Returns:
            Filtered list of most relevant follow-up questions
        """
        if len(questions) <= 1:
            return questions

        llm = self._llm_manager.get_utility_provider()

        questions_str = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

        system = """You are filtering research questions for architectural relevance."""

        prompt = f"""Root Query: {root_query}
Current Question: {current_query}

Candidate Follow-ups:
{questions_str}

Select the questions that:
1. Help understand system architecture (component interactions, data flow)
2. Are directly related to code elements already found
3. Deepen understanding of the ROOT query (not tangents)

Return ONLY the question numbers (comma-separated, e.g., "1,3") for the most relevant questions.
Maximum {MAX_FOLLOWUP_QUESTIONS} questions."""

        try:
            response = await llm.complete(prompt, system=system, max_completion_tokens=1000)
            # Parse selected indices
            selected = [
                int(n.strip()) - 1
                for n in response.content.replace(",", " ").split()
                if n.strip().isdigit()
            ]
            filtered = [questions[i] for i in selected if 0 <= i < len(questions)]

            if filtered:
                logger.debug(
                    f"Filtered {len(questions)} follow-ups to {len(filtered)} relevant ones"
                )
                return filtered[:MAX_FOLLOWUP_QUESTIONS]
        except Exception as e:
            logger.warning(f"Follow-up filtering failed: {e}, using all questions")

        return questions[:MAX_FOLLOWUP_QUESTIONS]

    def _calculate_max_depth(self) -> int:
        """Calculate max depth based on repository size.

        Returns:
            Max depth for BFS traversal
        """
        # Get total LOC from database
        stats = self._db_services.provider.get_stats()
        total_chunks = stats.get("chunks", 0)

        # Rough estimation: 1 chunk ≈ 20 LOC
        estimated_loc = total_chunks * 20

        if estimated_loc < 100_000:
            return 3
        elif estimated_loc < 1_000_000:
            return 4
        elif estimated_loc < 10_000_000:
            return 5
        else:
            # Each order of magnitude adds +1
            magnitude = math.log10(estimated_loc)
            return int(3 + (magnitude - 5))

    def _get_adaptive_token_budgets(
        self, depth: int, max_depth: int, is_leaf: bool
    ) -> dict[str, int]:
        """Calculate adaptive token budgets based on node depth and tree position.

        Strategy (LLM×MapReduce Pyramid):
        - Leaves: Dense implementation details (10-12k tokens) - focused analysis
        - Internal nodes: Progressive compression toward root
        - Root: Concise synthesis (5-8k tokens target) - practical overview

        The deeper the node during expansion, the more detail needed.
        As we collapse upward during synthesis, we compress while maintaining quality.

        Args:
            depth: Current node depth (0 = root)
            max_depth: Maximum depth for this codebase (3-7 typically)
            is_leaf: Whether this is a leaf node

        Returns:
            Dictionary with adaptive token budgets for this node
        """
        if not ENABLE_ADAPTIVE_BUDGETS:
            # Fallback to legacy fixed budgets
            return {
                "file_content_tokens": MAX_FILE_CONTENT_TOKENS,
                "llm_input_tokens": MAX_LLM_INPUT_TOKENS,
                "answer_tokens": MAX_LEAF_ANSWER_TOKENS
                if is_leaf
                else MAX_SYNTHESIS_TOKENS,
            }

        # Normalize depth: 0.0 at root, 1.0 at max_depth
        depth_ratio = depth / max(max_depth, 1)

        # INPUT BUDGETS (what LLM sees - file content and total input)
        # ==============================================================

        # File content budget: Scales with depth (10k → 50k tokens)
        # Root needs LESS raw code (synthesizing), leaves need MORE (analyzing)
        file_content_tokens = int(
            FILE_CONTENT_TOKENS_MIN
            + (FILE_CONTENT_TOKENS_MAX - FILE_CONTENT_TOKENS_MIN) * depth_ratio
        )

        # LLM total input budget (query + context + code): 15k → 60k tokens
        llm_input_tokens = int(
            LLM_INPUT_TOKENS_MIN
            + (LLM_INPUT_TOKENS_MAX - LLM_INPUT_TOKENS_MIN) * depth_ratio
        )

        # OUTPUT BUDGETS (what LLM generates)
        # ====================================

        if is_leaf:
            # LEAVES: Dense, focused detail (10-12k tokens)
            # Scale slightly with depth to handle variable max_depth (3-7)
            answer_tokens = int(
                LEAF_ANSWER_TOKENS_BASE + LEAF_ANSWER_TOKENS_BONUS * depth_ratio
            )
        else:
            # INTERNAL NODES: Compress as we go UP the tree
            # Root (depth 0) gets concise output (5k)
            # Deeper internal nodes get more budget before compressing
            answer_tokens = int(
                INTERNAL_ROOT_TARGET
                + (INTERNAL_MAX_TOKENS - INTERNAL_ROOT_TARGET) * depth_ratio
            )

        logger.debug(
            f"Adaptive budgets for depth {depth}/{max_depth} ({'leaf' if is_leaf else 'internal'}): "
            f"file={file_content_tokens:,}, input={llm_input_tokens:,}, output={answer_tokens:,}"
        )

        return {
            "file_content_tokens": file_content_tokens,
            "llm_input_tokens": llm_input_tokens,
            "answer_tokens": answer_tokens,
        }

    def _get_next_node_id(self) -> int:
        """Get next node ID for graph traversal."""
        self._node_counter += 1
        return self._node_counter
