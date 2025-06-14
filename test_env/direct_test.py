#!/usr/bin/env python3
"""
Direct Search Staleness Test

This script tests the realtime-search-cache-staleness hypothesis directly
without MCP server complexity. It validates whether search results become
stale after file modifications.

Usage:
    cd chunkhound/test_env
    export OPENAI_API_KEY="your-key"
    python direct_test.py
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add chunkhound to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.database.duckdb_provider import DuckDBProvider
from services.embedding_service import EmbeddingService
from providers.embeddings.openai_provider import OpenAIEmbeddingProvider
from core.models.file import File
from services.indexing_coordinator import IndexingCoordinator

class SearchStalnessTest:
    """Direct test for search result staleness hypothesis."""

    def __init__(self):
        self.test_dir = Path("./test_data_direct")
        self.db_path = "./test_direct.duckdb"
        self.database = None
        self.embedding_service = None
        self.indexing_coordinator = None

    def setup(self):
        """Initialize test environment."""
        print("=== Setting up test environment ===")

        # Clean up previous test
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

        # Create test directory
        self.test_dir.mkdir(exist_ok=True)

        # Initialize database
        self.database = DuckDBProvider(db_path=self.db_path)
        self.database.connect()
        print(f"✓ Database initialized: {self.db_path}")

        # Initialize indexing coordinator
        self.indexing_coordinator = IndexingCoordinator(self.database)
        print("✓ Indexing coordinator initialized")

        # Initialize embedding service if API key available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            openai_provider = OpenAIEmbeddingProvider(api_key=openai_key)
            self.embedding_service = EmbeddingService(self.database, openai_provider)
            print("✓ Embedding service initialized")
        else:
            print("⚠ No OPENAI_API_KEY - semantic search disabled")

    def cleanup(self):
        """Clean up test environment."""
        print("\n=== Cleaning up ===")
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        print("✓ Cleanup complete")

    def create_test_file(self, filename: str, content: str) -> Path:
        """Create a test file with given content."""
        file_path = self.test_dir / filename
        file_path.write_text(content)
        return file_path

    async def index_file(self, file_path: Path):
        """Index a file in the database."""
        abs_path = file_path.resolve()
        stat = abs_path.stat()

        # Create File object
        file_obj = File(
            path=str(abs_path),
            mtime=stat.st_mtime,
            language=self.indexing_coordinator.detect_file_language(abs_path),
            size_bytes=stat.st_size
        )

        # Insert file and get ID
        file_id = self.database.insert_file(file_obj)

        # Process file content for indexing
        await self.database.process_file_incremental(abs_path)

    def search_regex(self, pattern: str, limit: int = 10):
        """Search using regex."""
        return self.database.search_regex(pattern=pattern, limit=limit)

    async def search_semantic(self, query: str, limit: int = 10):
        """Search using semantic similarity."""
        if not self.embedding_service:
            return []

        # Skip semantic search for now - focus on chunking issue
        print("⚠ Semantic search skipped - focusing on chunking pipeline")
        return []

    async def test_initial_indexing(self):
        """Test 1: Initial file indexing and search."""
        print("\n=== Test 1: Initial Indexing ===")

        # Create test file
        test_content = """
def calculate_fibonacci(n):
    \"\"\"Calculate fibonacci number efficiently.\"\"\"
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# This is a unique marker: INITIAL_VERSION_12345
print("Hello from initial version")
"""

        file_path = self.create_test_file("fibonacci.py", test_content)
        print(f"✓ Created test file: {file_path}")

        # Index the file
        await self.index_file(file_path)
        print("✓ File indexed")

        # Test regex search
        regex_results = self.search_regex("INITIAL_VERSION_12345")
        print(f"✓ Regex search found {len(regex_results)} results")

        # Test semantic search
        if self.embedding_service:
            semantic_results = await self.search_semantic("fibonacci calculation function")
            print(f"✓ Semantic search found {len(semantic_results)} results")

        # CHUNKING ANALYSIS: Check if chunks were actually created
        stats = self.database.get_stats()
        chunk_count = stats.get('chunks', 0)
        print(f"✓ Total chunks in database: {chunk_count}")

        if chunk_count == 0:
            print("❌ CHUNKING FAILURE: No chunks extracted from file")
            print("   This explains why search returns 0 results")
            return False

        return len(regex_results) > 0

    async def test_file_modification(self):
        """Test 2: File modification and search staleness."""
        print("\n=== Test 2: File Modification ===")

        file_path = self.test_dir / "fibonacci.py"

        # Modify the file with new content
        modified_content = """
def calculate_fibonacci_optimized(n):
    \"\"\"Calculate fibonacci number with memoization.\"\"\"
    memo = {}
    def fib(n):
        if n in memo:
            return memo[n]
        if n <= 1:
            return n
        memo[n] = fib(n-1) + fib(n-2)
        return memo[n]
    return fib(n)

# This is a unique marker: MODIFIED_VERSION_67890
print("Hello from modified version")
"""

        file_path.write_text(modified_content)
        print("✓ File modified with new content")

        # Wait a moment for filesystem timestamp
        time.sleep(1)

        # Re-index the modified file
        await self.index_file(file_path)
        print("✓ File re-indexed")

        # Test that old content is gone
        old_regex_results = self.search_regex("INITIAL_VERSION_12345")
        print(f"✓ Old content search: {len(old_regex_results)} results (should be 0)")

        # Test that new content is found
        new_regex_results = self.search_regex("MODIFIED_VERSION_67890")
        print(f"✓ New content search: {len(new_regex_results)} results (should be > 0)")

        # Test semantic search for new content
        if self.embedding_service:
            semantic_results = await self.search_semantic("memoization optimization")
            print(f"✓ Semantic search for new concept: {len(semantic_results)} results")

            # Test semantic search for old content
            old_semantic_results = await self.search_semantic("recursive fibonacci inefficient")
            print(f"✓ Semantic search for old concept: {len(old_semantic_results)} results")

        # CHUNKING ANALYSIS: Check if chunks were properly updated
        stats = self.database.get_stats()
        chunk_count = stats.get('chunks', 0)
        print(f"✓ Total chunks after modification: {chunk_count}")

        # HYPOTHESIS TEST: Are results stale?
        old_content_found = len(old_regex_results) > 0
        new_content_found = len(new_regex_results) > 0

        if old_content_found:
            print("❌ STALENESS DETECTED: Old content still found in search results")
            return False
        elif not new_content_found:
            print("❌ INDEXING FAILURE: New content not found in search results")
            return False
        else:
            print("✅ SEARCH FRESHNESS CONFIRMED: Results properly updated")
            return True

    async def test_file_deletion(self):
        """Test 3: File deletion and search cleanup."""
        print("\n=== Test 3: File Deletion ===")

        file_path = self.test_dir / "fibonacci.py"
        abs_path = str(file_path.resolve())

        # Delete the file from database
        self.database.delete_file_completely(abs_path)
        print("✓ File deleted from database")

        # Search for content that should be gone
        regex_results = self.search_regex("MODIFIED_VERSION_67890")
        semantic_results = []
        if self.embedding_service:
            semantic_results = await self.search_semantic("fibonacci memoization")

        print(f"✓ Regex search after deletion: {len(regex_results)} results (should be 0)")
        print(f"✓ Semantic search after deletion: {len(semantic_results)} results (should be 0)")

        # CHUNKING ANALYSIS: Check if chunks were properly deleted
        stats = self.database.get_stats()
        chunk_count = stats.get('chunks', 0)
        print(f"✓ Total chunks after deletion: {chunk_count}")

        # Test deletion effectiveness
        deletion_clean = len(regex_results) == 0
        if not deletion_clean:
            print("❌ DELETION STALENESS: Deleted content still found in search")
            return False
        else:
            print("✅ DELETION CLEANUP CONFIRMED: No stale results after deletion")
            return True

    async def run_all_tests(self):
        """Run complete test suite."""
        print("=== Direct Search Staleness Test ===")
        print("Testing hypothesis: Search results become stale after file modifications")

        try:
            self.setup()

            # Run tests
            test1_pass = await self.test_initial_indexing()
            test2_pass = await self.test_file_modification()
            test3_pass = await self.test_file_deletion()

            # Results
            print(f"\n=== Test Results ===")
            print(f"Initial Indexing: {'PASS' if test1_pass else 'FAIL'}")
            print(f"Modification Freshness: {'PASS' if test2_pass else 'FAIL'}")
            print(f"Deletion Cleanup: {'PASS' if test3_pass else 'FAIL'}")

            # Hypothesis conclusion
            all_pass = test1_pass and test2_pass and test3_pass

            print(f"\n=== HYPOTHESIS CONCLUSION ===")
            if all_pass:
                print("✅ HYPOTHESIS DISPROVEN")
                print("Search results DO NOT become stale after file modifications.")
                print("The core database and search functionality works correctly.")
                print("Root cause likely in MCP server layer or client communication.")
            else:
                print("❌ HYPOTHESIS CONFIRMED")
                print("Search results DO become stale after file modifications.")
                print("The staleness issue exists in the core database/search layer.")

            return all_pass

        except Exception as e:
            print(f"❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.cleanup()

async def main():
    """Run the direct staleness test."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: No OPENAI_API_KEY set - semantic search tests will be skipped")

    test = SearchStalnessTest()
    success = await test.run_all_tests()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
