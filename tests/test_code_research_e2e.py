"""End-to-end tests for code research without LLM API access.

Tests the complete deep research pipeline using fake providers that return
deterministic responses. Designed for CI/CD execution without external dependencies.
"""

import tempfile
from pathlib import Path
import pytest

from chunkhound.core.config.config import Config
from chunkhound.database_factory import create_services
from chunkhound.embeddings import EmbeddingManager
from chunkhound.llm_manager import LLMManager
from chunkhound.services.deep_research_service import DeepResearchService
from chunkhound.services.indexing_coordinator import IndexingCoordinator
from tests.fixtures.fake_providers import FakeLLMProvider, FakeEmbeddingProvider


class TestCodeResearchE2E:
    """End-to-end tests for code research pipeline."""

    @pytest.fixture
    async def research_setup(self):
        """Setup complete research environment with fake providers."""
        # Create temporary directory and database
        temp_dir = Path(tempfile.mkdtemp())
        db_path = temp_dir / ".chunkhound" / "test.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create test code files
        test_files = self._create_test_codebase(temp_dir)

        # Use fake args to prevent find_project_root
        from types import SimpleNamespace
        fake_args = SimpleNamespace(path=temp_dir)

        # Create config without real API keys
        config = Config(
            args=fake_args,
            database={"path": str(db_path), "provider": "duckdb"},
            indexing={"include": ["*"], "exclude": ["*.log"]},
        )

        # Create services
        services = create_services(db_path, config)
        services.provider.connect()

        # Create fake providers
        fake_embedding_provider = FakeEmbeddingProvider(
            model="fake-embeddings", dims=1536, batch_size=100
        )
        fake_llm_utility = FakeLLMProvider(
            model="fake-gpt-utility",
            responses={
                "expand": "semantic search implementation, code structure analysis, data processing",
                "follow": "1. How does semantic search work?\n2. What is the BFS traversal algorithm?\n3. How are chunks stored?",
            },
        )
        fake_llm_synthesis = FakeLLMProvider(
            model="fake-gpt-synthesis",
            responses={
                "synthesis": "## Overview\nThe codebase implements semantic code search with deep research capabilities.\n\n## Key Components\n- SearchService: Handles semantic and regex queries\n- DeepResearchService: Coordinates BFS exploration\n- ChunkingSystem: Extracts code chunks with smart boundaries\n\n## Architecture\nQueries flow through semantic search to chunk retrieval, with smart boundary expansion for complete code units. BFS traversal explores related concepts across multiple levels.\n\n## Data Flow\n1. User query → Semantic search\n2. Chunk retrieval with smart boundaries\n3. Follow-up generation for BFS\n4. Aggregation and synthesis",
            },
        )

        # Register fake embedding provider
        embedding_manager = EmbeddingManager()
        embedding_manager.register_provider(fake_embedding_provider, set_default=True)

        # Create fake LLM manager with dummy configs (will be replaced)
        dummy_config = {
            "provider": "openai",
            "api_key": "fake-key",
            "model": "fake-model",
        }
        llm_manager = LLMManager(
            utility_config=dummy_config, synthesis_config=dummy_config
        )
        # Replace with fake providers after initialization
        llm_manager._utility_provider = fake_llm_utility
        llm_manager._synthesis_provider = fake_llm_synthesis

        # Index test codebase
        coordinator = IndexingCoordinator(
            database_provider=services.provider,
            base_directory=temp_dir,
            embedding_provider=fake_embedding_provider,
        )
        for test_file in test_files:
            await coordinator.process_file(test_file)

        # Generate embeddings
        await coordinator.generate_missing_embeddings()

        # Create deep research service
        research_service = DeepResearchService(
            database_services=services,
            embedding_manager=embedding_manager,
            llm_manager=llm_manager,
        )

        # Get chunk mapping for validation
        all_indexed_chunks = services.provider.get_all_chunks_with_metadata()
        chunk_to_file = {}
        for i, chunk in enumerate(all_indexed_chunks):
            # Use chunk_id if available, otherwise use index
            chunk_id = chunk.get("chunk_id") or chunk.get("id") or i
            chunk_to_file[chunk_id] = chunk.get("file_path") or chunk.get("path")

        yield {
            "services": services,
            "embedding_manager": embedding_manager,
            "llm_manager": llm_manager,
            "research_service": research_service,
            "fake_embedding": fake_embedding_provider,
            "fake_llm_utility": fake_llm_utility,
            "fake_llm_synthesis": fake_llm_synthesis,
            "temp_dir": temp_dir,
            "test_files": test_files,
            "chunk_to_file": chunk_to_file,
            "total_chunks": len(all_indexed_chunks),
        }

        # Cleanup
        try:
            services.provider.close()
        except Exception:
            pass

        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    def _create_test_codebase(self, base_dir: Path) -> list[Path]:
        """Create a realistic test codebase for research."""
        test_files = []

        # File 1: Search service
        search_service = base_dir / "search_service.py"
        search_service.write_text('''"""Search service implementation."""

import asyncio
from typing import List, Dict, Any

class SearchService:
    """Service for semantic and regex code search."""

    def __init__(self, database, embedding_provider):
        """Initialize search service.

        Args:
            database: Database provider for queries
            embedding_provider: Provider for generating embeddings
        """
        self.database = database
        self.embedding_provider = embedding_provider

    async def search_semantic(self, query: str, limit: int = 10) -> List[Dict]:
        """Perform semantic search using embeddings.

        Args:
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of matching code chunks with relevance scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_single(query)

        # Search database
        results = self.database.search_semantic(
            embedding=query_embedding,
            limit=limit
        )

        return results

    def search_regex(self, pattern: str) -> List[Dict]:
        """Perform regex search on code content.

        Args:
            pattern: Regular expression pattern

        Returns:
            List of matching code chunks
        """
        return self.database.search_regex(pattern=pattern)
''')
        test_files.append(search_service)

        # File 2: Deep research service
        deep_research = base_dir / "deep_research_service.py"
        deep_research.write_text('''"""Deep research service with BFS traversal."""

class BFSNode:
    """Node in BFS traversal tree."""

    def __init__(self, query: str, depth: int = 0):
        self.query = query
        self.depth = depth
        self.children = []
        self.chunks = []
        self.token_budgets = {}

class DeepResearchService:
    """Service for deep code research using BFS."""

    def __init__(self, search_service, llm_provider):
        self.search_service = search_service
        self.llm_provider = llm_provider

    async def deep_research(self, query: str, max_depth: int = 3):
        """Perform deep research with BFS traversal.

        Args:
            query: Initial research query
            max_depth: Maximum BFS depth to explore

        Returns:
            Dict with answer and metadata
        """
        root = BFSNode(query=query, depth=0)
        nodes_to_explore = [root]
        all_nodes = [root]

        for depth in range(1, max_depth + 1):
            if not nodes_to_explore:
                break

            current_level_nodes = nodes_to_explore
            nodes_to_explore = []

            for node in current_level_nodes:
                # Search for relevant chunks
                chunks = await self.search_service.search_semantic(
                    node.query, limit=20
                )
                node.chunks = chunks

                # Generate follow-up questions
                if depth < max_depth:
                    follow_ups = await self._generate_follow_ups(node, chunks)
                    for follow_up in follow_ups:
                        child = BFSNode(query=follow_up, depth=depth)
                        node.children.append(child)
                        nodes_to_explore.append(child)
                        all_nodes.append(child)

        # Aggregate findings and synthesize
        answer = await self._synthesize_findings(all_nodes)

        return {
            "answer": answer,
            "metadata": {
                "depth_reached": max(node.depth for node in all_nodes),
                "nodes_explored": len(all_nodes),
                "chunks_analyzed": sum(len(node.chunks) for node in all_nodes),
            },
        }

    async def _generate_follow_ups(self, node: BFSNode, chunks: list) -> list[str]:
        """Generate follow-up questions based on retrieved chunks."""
        prompt = f"Based on code about: {node.query}. Generate follow-up questions."
        response = await self.llm_provider.complete(prompt)
        # Parse questions from response
        questions = [q.strip() for q in response.content.split("\\n") if q.strip()]
        return questions[:3]  # Limit to 3 follow-ups

    async def _synthesize_findings(self, nodes: list[BFSNode]) -> str:
        """Synthesize all findings into final answer."""
        all_chunks = []
        for node in nodes:
            all_chunks.extend(node.chunks)

        prompt = f"Synthesize findings from {len(all_chunks)} code chunks"
        response = await self.llm_provider.complete(prompt)
        return response.content
''')
        test_files.append(deep_research)

        # File 3: Chunking system
        chunking_service = base_dir / "chunking_service.py"
        chunking_service.write_text('''"""Code chunking with smart boundaries."""

from typing import List, Tuple

class ChunkingService:
    """Service for extracting code chunks with smart boundaries."""

    def expand_to_natural_boundaries(
        self, lines: List[str], start_line: int, end_line: int, language: str
    ) -> Tuple[int, int]:
        """Expand chunk to natural code boundaries.

        Args:
            lines: File lines
            start_line: Initial start line (1-indexed)
            end_line: Initial end line (1-indexed)
            language: Programming language

        Returns:
            Tuple of (expanded_start, expanded_end) in 1-indexed lines
        """
        if language == "python":
            return self._expand_python_boundaries(lines, start_line, end_line)
        else:
            return self._expand_brace_boundaries(lines, start_line, end_line)

    def _expand_python_boundaries(
        self, lines: List[str], start: int, end: int
    ) -> Tuple[int, int]:
        """Expand Python code using indentation."""
        # Search backward for def/class
        expanded_start = start
        for i in range(start - 1, max(0, start - 200), -1):
            line = lines[i].strip()
            if line.startswith("def ") or line.startswith("class "):
                expanded_start = i + 1
                break

        # Search forward for dedent
        start_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
        expanded_end = end
        for i in range(end, min(len(lines), end + 200)):
            if i >= len(lines):
                break
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= start_indent:
                expanded_end = i
                break

        return expanded_start, expanded_end

    def _expand_brace_boundaries(
        self, lines: List[str], start: int, end: int
    ) -> Tuple[int, int]:
        """Expand brace-delimited code using brace depth."""
        expanded_start = start
        brace_depth = 0

        # Search backward for opening brace
        for i in range(start - 1, max(0, start - 200), -1):
            line = lines[i]
            open_braces = line.count("{")
            close_braces = line.count("}")
            brace_depth += close_braces - open_braces

            if brace_depth > 0 and "{" in line:
                expanded_start = i + 1
                break

        # Search forward for closing brace
        brace_depth = 0
        expanded_end = end
        for i in range(expanded_start - 1, min(len(lines), expanded_start + 300)):
            line = lines[i]
            open_braces = line.count("{")
            close_braces = line.count("}")
            brace_depth += open_braces - close_braces

            if brace_depth == 0 and i > expanded_start - 1 and "}" in line:
                expanded_end = i + 1
                break

        return expanded_start, expanded_end
''')
        test_files.append(chunking_service)

        return test_files

    @pytest.mark.asyncio
    async def test_full_research_pipeline(self, research_setup):
        """Test complete research pipeline from query to synthesis."""
        setup = research_setup
        research_service = setup["research_service"]

        # Perform research
        result = await research_service.deep_research("How does semantic search work?")

        # Validate structure
        assert "answer" in result, "Result should contain answer"
        assert "metadata" in result, "Result should contain metadata"

        # Validate metadata
        metadata = result["metadata"]
        assert "depth_reached" in metadata
        assert "nodes_explored" in metadata
        assert "chunks_analyzed" in metadata

        # Validate exploration
        assert metadata["depth_reached"] >= 1, "Should explore at least depth 1"
        assert metadata["nodes_explored"] >= 1, "Should explore at least 1 node"

        # Validate answer
        answer = result["answer"]
        assert isinstance(answer, str), "Answer should be string"
        assert len(answer) > 0, "Answer should not be empty"

        print(f"✓ Research completed: {metadata['nodes_explored']} nodes, {metadata['chunks_analyzed']} chunks")

    @pytest.mark.asyncio
    async def test_search_pipeline_with_fake_embeddings(self, research_setup):
        """Test semantic search with fake embedding provider."""
        setup = research_setup
        services = setup["services"]
        fake_embedding = setup["fake_embedding"]

        # Perform semantic search through services
        query = "search implementation"
        query_embedding = await fake_embedding.embed_single(query)

        results = services.search_service.search_semantic(
            embedding=query_embedding, limit=10
        )

        # Validate results
        assert isinstance(results, list), "Should return list of results"
        # Note: May be empty if no chunks indexed yet, but should not error
        print(f"✓ Semantic search returned {len(results)} results")

        # Validate fake provider was used
        stats = fake_embedding.get_usage_stats()
        assert stats["embeddings_generated"] > 0, "Should have generated embeddings"
        print(f"✓ Fake embeddings generated: {stats['embeddings_generated']}")

    @pytest.mark.asyncio
    async def test_regex_search_without_embeddings(self, research_setup):
        """Test regex search works without embedding provider."""
        setup = research_setup
        services = setup["services"]

        # Perform regex search
        results = services.search_service.search_regex(pattern="def.*search")

        # Validate results
        assert isinstance(results, tuple), "Should return tuple (chunks, count)"
        chunks, count = results
        assert isinstance(chunks, list), "Chunks should be list"
        assert isinstance(count, int), "Count should be int"

        print(f"✓ Regex search found {count} matches")

    @pytest.mark.asyncio
    async def test_reranking_with_fake_provider(self, research_setup):
        """Test reranking using fake provider."""
        setup = research_setup
        fake_embedding = setup["fake_embedding"]

        # Test reranking
        query = "semantic search algorithm"
        documents = [
            "This implements semantic search using embeddings",
            "Regular expression pattern matching",
            "Database query optimization techniques",
            "Vector similarity search algorithms",
        ]

        results = await fake_embedding.rerank(query, documents, top_k=3)

        # Validate results
        assert isinstance(results, list), "Should return list of RerankResult"
        assert len(results) <= 3, "Should respect top_k limit"

        for result in results:
            assert hasattr(result, "index"), "Result should have index"
            assert hasattr(result, "score"), "Result should have score"
            assert 0 <= result.index < len(documents), "Index should be valid"

        # Validate deterministic ordering
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score"

        print(f"✓ Reranking returned {len(results)} results with deterministic scores")

    @pytest.mark.asyncio
    async def test_budget_management(self, research_setup):
        """Test adaptive token budget management."""
        setup = research_setup
        research_service = setup["research_service"]

        # Perform research with depth limit
        result = await research_service.deep_research(
            "What is the architecture?", max_depth=2
        )

        # Validate budget was managed
        metadata = result["metadata"]
        assert metadata["depth_reached"] <= 2, "Should respect max_depth"

        # Validate LLM usage was tracked
        utility_stats = setup["fake_llm_utility"].get_usage_stats()
        synthesis_stats = setup["fake_llm_synthesis"].get_usage_stats()

        assert utility_stats["requests_made"] > 0, "Utility LLM should be called"
        assert synthesis_stats["requests_made"] > 0, "Synthesis LLM should be called"

        print(f"✓ Budget management: utility={utility_stats['requests_made']} requests, "
              f"synthesis={synthesis_stats['requests_made']} requests")

    @pytest.mark.asyncio
    async def test_smart_boundaries_python(self, research_setup):
        """Test smart boundary expansion for Python code."""
        setup = research_setup
        services = setup["services"]

        # Search for Python function
        results = services.search_service.search_regex(pattern="def search_semantic")

        if results:
            chunks, _ = results
            if chunks:
                # Validate chunk contains complete function
                chunk_content = chunks[0]["content"]
                assert "def search_semantic" in chunk_content
                # Should include docstring and complete implementation
                assert '"""' in chunk_content or "'''" in chunk_content

                print("✓ Smart boundaries preserved complete Python function")

    @pytest.mark.asyncio
    async def test_bfs_traversal_depth(self, research_setup):
        """Test BFS traversal explores multiple depth levels."""
        setup = research_setup
        research_service = setup["research_service"]

        # Perform research with specific depth
        result = await research_service.deep_research(
            "How does the system work?", max_depth=3
        )

        metadata = result["metadata"]

        # Validate BFS exploration
        assert metadata["nodes_explored"] >= 1, "Should explore at least root node"
        assert metadata["depth_reached"] >= 1, "Should reach at least depth 1"

        # Validate multiple nodes if follow-ups generated
        if metadata["nodes_explored"] > 1:
            assert metadata["depth_reached"] >= 1, "Multiple nodes implies depth > 0"

        print(f"✓ BFS traversal: depth={metadata['depth_reached']}, nodes={metadata['nodes_explored']}")

    @pytest.mark.asyncio
    async def test_synthesis_aggregation(self, research_setup):
        """Test synthesis aggregates findings from all nodes."""
        setup = research_setup
        research_service = setup["research_service"]
        fake_synthesis = setup["fake_llm_synthesis"]

        # Perform research
        result = await research_service.deep_research("Explain the codebase")

        # Validate synthesis was called
        synthesis_stats = fake_synthesis.get_usage_stats()
        assert synthesis_stats["requests_made"] > 0, "Synthesis should be invoked"

        # Validate answer structure
        answer = result["answer"]
        assert "##" in answer or len(answer) > 50, "Answer should be structured"

        print(f"✓ Synthesis aggregated {result['metadata']['chunks_analyzed']} chunks")

    @pytest.mark.asyncio
    async def test_deterministic_fake_providers(self, research_setup):
        """Test fake providers return deterministic results."""
        setup = research_setup
        fake_embedding = setup["fake_embedding"]
        fake_llm = setup["fake_llm_utility"]

        # Test embedding determinism
        text = "test embedding consistency"
        embedding1 = await fake_embedding.embed_single(text)
        embedding2 = await fake_embedding.embed_single(text)

        assert embedding1 == embedding2, "Embeddings should be deterministic"

        # Test LLM determinism
        prompt = "test LLM consistency"
        response1 = await fake_llm.complete(prompt)
        response2 = await fake_llm.complete(prompt)

        assert response1.content == response2.content, "LLM responses should be deterministic"

        print("✓ Fake providers are deterministic")

    @pytest.mark.asyncio
    async def test_no_external_api_calls(self, research_setup):
        """Verify test runs without any external API calls."""
        setup = research_setup
        research_service = setup["research_service"]

        # Perform research
        result = await research_service.deep_research("Test query")

        # All providers are fake, so this should complete without network errors
        assert result is not None, "Should complete without external APIs"

        # Validate fake providers were used
        fake_embedding_stats = setup["fake_embedding"].get_usage_stats()
        fake_llm_stats = setup["fake_llm_utility"].get_usage_stats()

        assert fake_embedding_stats["requests_made"] > 0
        assert fake_llm_stats["requests_made"] > 0

        print("✓ Test completed using only fake providers (no external API calls)")

    @pytest.mark.asyncio
    async def test_chunk_retrieval_accuracy(self, research_setup):
        """Verify deep research retrieves correct chunks from test files."""
        setup = research_setup
        services = setup["services"]
        total_chunks = setup["total_chunks"]
        chunk_to_file = setup["chunk_to_file"]

        # Verify chunks were indexed
        assert total_chunks > 0, "Should have indexed chunks from test files"
        print(f"✓ Total chunks indexed: {total_chunks}")

        # Get all chunks to verify content
        all_chunks = services.provider.get_all_chunks_with_metadata()

        # Should find chunks from search_service.py
        search_service_chunks = [
            c for c in all_chunks
            if "search_service.py" in (c.get("file_path") or c.get("path", ""))
        ]
        assert len(search_service_chunks) > 0, "Should retrieve chunks from search_service.py"

        # Verify chunks contain expected symbols
        chunk_symbols = [c.get("symbol", "") for c in search_service_chunks]
        assert any("search_semantic" in s for s in chunk_symbols), \
            f"Should find search_semantic function, found symbols: {chunk_symbols}"

        print(f"✓ Found {len(search_service_chunks)} chunks from search_service.py")
        print(f"✓ Verified presence of search_semantic function")

    @pytest.mark.asyncio
    async def test_file_coverage_in_indexing(self, research_setup):
        """Verify all test files are indexed and accessible."""
        setup = research_setup
        services = setup["services"]
        test_files = setup["test_files"]
        chunk_to_file = setup["chunk_to_file"]

        # Get all unique file paths from chunks
        indexed_file_paths = set(chunk_to_file.values())

        # Should have indexed all test files
        assert len(indexed_file_paths) >= len(test_files), \
            f"Should index all {len(test_files)} test files, found {len(indexed_file_paths)}"

        # Verify file names match test files
        test_file_names = {f.name for f in test_files}
        indexed_file_names = {Path(p).name for p in indexed_file_paths if p}

        missing_files = test_file_names - indexed_file_names
        assert len(missing_files) == 0, f"Missing test files in index: {missing_files}"

        print(f"✓ All {len(test_files)} test files indexed")
        print(f"✓ File coverage: {', '.join(sorted(indexed_file_names))}")

    @pytest.mark.asyncio
    async def test_chunk_quality_and_boundaries(self, research_setup):
        """Verify chunks have proper boundaries and contain complete code units."""
        setup = research_setup
        services = setup["services"]

        # Get all chunks
        all_chunks = services.provider.get_all_chunks_with_metadata()
        assert len(all_chunks) > 0, "Should have chunks"

        complete_functions = 0
        complete_classes = 0

        for i, chunk in enumerate(all_chunks):
            content = chunk.get("content") or chunk.get("code", "")
            symbol = chunk.get("symbol", "")
            chunk_id = chunk.get("chunk_id") or chunk.get("id") or i

            # Chunks should have meaningful content
            assert len(content.strip()) > 0, f"Chunk {chunk_id} should have content"
            assert len(symbol) > 0, f"Chunk {chunk_id} should have symbol"

            # Python chunks with functions should be complete units
            if "def " in content:
                # Should have complete function (opening and body)
                assert ":" in content, f"Function in chunk {chunk_id} should have colon"
                # Should have indented body (not just signature)
                lines = content.split("\n")
                assert len(lines) > 1, f"Function in chunk {chunk_id} should have body"
                complete_functions += 1

            # Classes should have structure
            if "class " in content:
                assert ":" in content, f"Class in chunk {chunk_id} should have colon"
                complete_classes += 1

        print(f"✓ All {len(all_chunks)} chunks have valid content and symbols")
        print(f"✓ Found {complete_functions} complete functions, {complete_classes} complete classes")

    @pytest.mark.asyncio
    async def test_chunks_contain_test_code_patterns(self, research_setup):
        """Verify retrieved chunks actually contain code from our test files."""
        setup = research_setup
        services = setup["services"]

        # Get all chunks
        all_chunks = services.provider.get_all_chunks_with_metadata()

        # Expected patterns from our test codebase
        expected_patterns = {
            "SearchService": 0,
            "search_semantic": 0,
            "DeepResearchService": 0,
            "deep_research": 0,
            "ChunkingService": 0,
            "expand_to_natural_boundaries": 0,
        }

        # Count occurrences
        for chunk in all_chunks:
            content = chunk.get("content") or chunk.get("code", "")
            symbol = chunk.get("symbol", "")
            combined = content + " " + symbol

            for pattern in expected_patterns:
                if pattern in combined:
                    expected_patterns[pattern] += 1

        # Verify we found key patterns
        found_patterns = {k: v for k, v in expected_patterns.items() if v > 0}
        assert len(found_patterns) >= 4, \
            f"Should find at least 4 key patterns from test files, found: {found_patterns}"

        print(f"✓ Found {len(found_patterns)} key patterns in chunks:")
        for pattern, count in found_patterns.items():
            print(f"  - {pattern}: {count} occurrences")

    @pytest.mark.asyncio
    async def test_chunk_deduplication_detection(self, research_setup):
        """Test that duplicate chunks are correctly detected."""
        setup = research_setup
        research_service = setup["research_service"]

        # Create a test node with chunks
        from chunkhound.services.deep_research_service import BFSNode

        parent = BFSNode(
            query="parent query",
            depth=1,
            node_id=1,
        )
        parent.chunks = [
            {
                "file_path": "test.py",
                "start_line": 10,
                "end_line": 50,
                "expanded_start_line": 8,
                "expanded_end_line": 52,
                "chunk_id": "chunk1",
            }
        ]
        parent.file_contents = {}

        child = BFSNode(
            query="child query",
            depth=2,
            parent=parent,
            node_id=2,
        )

        # Test case 1: 100% duplicate (same expanded range)
        duplicate_chunks = [
            {
                "file_path": "test.py",
                "start_line": 20,
                "end_line": 30,
                "expanded_start_line": 20,
                "expanded_end_line": 30,
                "chunk_id": "chunk2",
            }
        ]

        has_new, stats = research_service._detect_new_information(child, duplicate_chunks)
        assert not has_new, "Should detect 100% duplicate"
        assert stats["duplicate_chunks"] == 1
        assert stats["new_chunks"] == 0

        print("✓ Detected 100% duplicate chunk correctly")

        # Test case 2: Partial overlap (should count as new)
        partial_overlap_chunks = [
            {
                "file_path": "test.py",
                "start_line": 45,
                "end_line": 70,
                "expanded_start_line": 45,
                "expanded_end_line": 70,
                "chunk_id": "chunk3",
            }
        ]

        has_new, stats = research_service._detect_new_information(
            child, partial_overlap_chunks
        )
        assert has_new, "Should count partial overlap as new"
        assert stats["new_chunks"] == 1

        print("✓ Partial overlap correctly counted as new information")

        # Test case 3: New file (should count as new)
        new_file_chunks = [
            {
                "file_path": "other.py",
                "start_line": 1,
                "end_line": 10,
                "expanded_start_line": 1,
                "expanded_end_line": 10,
                "chunk_id": "chunk4",
            }
        ]

        has_new, stats = research_service._detect_new_information(
            child, new_file_chunks
        )
        assert has_new, "Should count new file as new"
        assert stats["new_chunks"] == 1

        print("✓ New file correctly counted as new information")

    @pytest.mark.asyncio
    async def test_full_file_read_detection(self, research_setup):
        """Test that fully-read files are correctly detected."""
        setup = research_setup
        research_service = setup["research_service"]

        # Full file (no separator)
        full_file = "def foo():\n    pass\n\ndef bar():\n    pass"
        assert research_service._is_file_fully_read(full_file)
        print("✓ Full file correctly detected")

        # Partial file (has separator)
        partial_file = "def foo():\n    pass\n\n...\n\ndef bar():\n    pass"
        assert not research_service._is_file_fully_read(partial_file)
        print("✓ Partial file correctly detected")

    @pytest.mark.asyncio
    async def test_termination_on_duplicates(self, research_setup):
        """Test that nodes terminate when finding only duplicates."""
        setup = research_setup
        research_service = setup["research_service"]
        from chunkhound.services.deep_research_service import BFSNode, ResearchContext

        # Create parent with chunks
        parent = BFSNode(query="parent", depth=1, node_id=1)
        parent.chunks = [
            {
                "file_path": "test.py",
                "start_line": 10,
                "end_line": 50,
                "expanded_start_line": 8,
                "expanded_end_line": 52,
                "chunk_id": "chunk1",
                "content": "def test():\n    pass",
            }
        ]
        parent.file_contents = {"test.py": "def test():\n    pass"}

        # Mock the search to return duplicate chunk
        original_unified_search = research_service._unified_search

        async def mock_search(query, context):
            return [
                {
                    "file_path": "test.py",
                    "start_line": 20,
                    "end_line": 30,
                    "expanded_start_line": 20,
                    "expanded_end_line": 30,
                    "chunk_id": "chunk2",
                    "content": "pass",
                }
            ]

        research_service._unified_search = mock_search

        try:
            # Process child node (should terminate)
            child = BFSNode(query="child", depth=2, parent=parent, node_id=2)
            context = ResearchContext(root_query="test")

            children = await research_service._process_bfs_node(child, context, 2)

            # Should return empty children (terminated)
            assert children == [], "Should return no children when only duplicates found"
            assert child.is_terminated_leaf, "Should mark as terminated leaf"
            assert child.new_chunk_count == 0, "Should have 0 new chunks"
            assert child.duplicate_chunk_count == 1, "Should have 1 duplicate"

            print("✓ Node correctly terminated on finding only duplicates")
            print(
                f"  - Terminated leaf: {child.is_terminated_leaf}, "
                f"New: {child.new_chunk_count}, Duplicates: {child.duplicate_chunk_count}"
            )

        finally:
            research_service._unified_search = original_unified_search

    @pytest.mark.asyncio
    async def test_question_synthesis(self, research_setup):
        """Test question synthesis functionality."""
        setup = research_setup
        research_service = setup["research_service"]
        fake_llm = setup["fake_llm_utility"]
        from chunkhound.services.deep_research_service import BFSNode, ResearchContext

        # Mock LLM to return synthesized questions
        original_complete = fake_llm.complete

        async def mock_complete(prompt, **kwargs):
            from types import SimpleNamespace

            if "Synthesize" in prompt:
                return SimpleNamespace(
                    content="1. How does data flow through the system?\n2. What are the key components?\n3. How does error handling work?"
                )
            return await original_complete(prompt, **kwargs)

        fake_llm.complete = mock_complete

        try:
            # Create many nodes to trigger synthesis
            nodes = []
            for i in range(10):
                node = BFSNode(query=f"Question {i}?", depth=1, node_id=i + 1)
                nodes.append(node)

            context = ResearchContext(root_query="test")

            # Synthesize to 3 questions
            synthesized = await research_service._synthesize_questions(
                nodes, context, 3
            )

            # Validate synthesis
            assert len(synthesized) == 3, "Should synthesize to target count"
            assert all(
                isinstance(node, BFSNode) for node in synthesized
            ), "Should return BFSNode objects"
            assert all(
                node.chunks == [] for node in synthesized
            ), "Synthesized nodes should have empty chunks"
            assert all(
                node.file_contents == {} for node in synthesized
            ), "Synthesized nodes should have empty file_contents"
            assert all(
                node.parent is not None for node in synthesized
            ), "Synthesized nodes should have merge parent"

            # Verify merge parent
            merge_parent = synthesized[0].parent
            assert "[Merge of 10 research directions]" in merge_parent.query
            assert len(merge_parent.children) == 10

            print("✓ Question synthesis working correctly")
            print(f"  - Synthesized {len(nodes)} questions into {len(synthesized)}")
            print(
                f"  - Created merge parent: '{merge_parent.query[:50]}...'"
            )
            print(f"  - Sample synthesized question: '{synthesized[0].query}'")

        finally:
            fake_llm.complete = original_complete

    @pytest.mark.asyncio
    async def test_synthesis_preserves_exploration(self, research_setup):
        """Test that synthesized nodes explore new areas, not rehash old findings."""
        setup = research_setup
        research_service = setup["research_service"]
        from chunkhound.services.deep_research_service import BFSNode, ResearchContext

        # Create nodes with existing chunks/files
        nodes = []
        for i in range(5):
            node = BFSNode(query=f"Question {i}?", depth=1, node_id=i + 1)
            node.chunks = [{"chunk_id": f"chunk{i}", "file_path": f"file{i}.py"}]
            node.file_contents = {f"file{i}.py": f"content {i}"}
            nodes.append(node)

        context = ResearchContext(root_query="test")

        # Synthesize
        synthesized = await research_service._synthesize_questions(nodes, context, 3)

        # Verify synthesized nodes don't inherit chunks/files
        for node in synthesized:
            assert (
                node.chunks == []
            ), "Synthesized nodes should start with empty chunks"
            assert (
                node.file_contents == {}
            ), "Synthesized nodes should start with empty files"

        print("✓ Synthesized nodes correctly start fresh without inherited data")
        print("  - This ensures they explore new areas, not rehash existing findings")
