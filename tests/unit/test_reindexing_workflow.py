"""
Tests for database re-indexing workflow and chunk preservation.

Tests the core logic for updating file content while preserving
unchanged chunks and their embeddings.
"""

import asyncio
import re
import tempfile
import shutil
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch, AsyncMock

import pytest

from chunkhound.core.config.config import Config
from chunkhound.database_factory import create_database_with_dependencies
from chunkhound.embeddings import EmbeddingManager


def generate_unique_content(marker):
    """Generate unique content for testing."""
    return f'''def {marker}_function():
    """This is a {marker} test function."""
    return "{marker}_result"

class {marker.title()}Class:
    """A {marker} test class."""
    
    def method1(self):
        return "{marker}_method1"
    
    def method2(self):
        return "{marker}_method2"
'''


# Regex-based content matching helpers
def find_function_definitions(content: str) -> List[str]:
    """Extract function names from content regardless of storage format."""
    pattern = r'def\s+(\w+)\s*\('
    return re.findall(pattern, content, re.IGNORECASE)


def find_class_definitions(content: str) -> List[str]:
    """Extract class names from content."""
    pattern = r'class\s+(\w+)\s*:'
    return re.findall(pattern, content, re.IGNORECASE)


def has_return_with_pattern(content: str, pattern: str) -> bool:
    """Check if content has return statement matching pattern."""
    return_pattern = f'return\\s+["\'].*{pattern}.*["\']'
    return bool(re.search(return_pattern, content, re.IGNORECASE))


def content_contains_identifier(content: str, identifier: str) -> bool:
    """Check if content contains identifier (word boundary)."""
    pattern = f'\\b{re.escape(identifier)}\\b'
    return bool(re.search(pattern, content, re.IGNORECASE))


def has_function_with_pattern(content: str, pattern: str) -> bool:
    """Check if content has function definition matching pattern."""
    func_pattern = f'def\\s+\\w*{re.escape(pattern)}\\w*\\s*\\('
    return bool(re.search(func_pattern, content, re.IGNORECASE))


class TestChunkPreservationLogic:
    """Test chunk preservation during re-indexing."""

    def setup_method(self):
        """Setup test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_reindex.db"

        # Create database
        config = Config(
            database={"path": str(self.db_path), "provider": "duckdb"},
            embedding={"provider": "openai", "model": "text-embedding-3-small"},
        )

        self.embedding_manager = EmbeddingManager()
        self.db = create_database_with_dependencies(
            db_path=self.db_path,
            config=config.to_dict(),
            embedding_manager=self.embedding_manager,
        )

    def teardown_method(self):
        """Cleanup test database."""
        if hasattr(self, "db"):
            self.db.close()

        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_chunks_for_file(self, file_path):
        """Helper to get chunks for a file using correct API."""
        file_record = self.db.get_file_by_path(str(file_path))
        if not file_record:
            return []
        return self.db.get_chunks_by_file_id(file_record['id'])

    @pytest.mark.asyncio
    async def test_chunk_preservation_identical_content(self):
        """Test that identical chunks are preserved."""
        file_path = self.temp_dir / "test_preserve.py"
        original_content = """def function1():
    return "hello"

def function2():
    return "world"
"""

        # Write and index original content
        file_path.write_text(original_content)
        await self.db.process_file(file_path)

        # Get original chunks
        original_chunks = self._get_chunks_for_file(str(file_path))
        assert len(original_chunks) > 0, "Should have chunks for original file"

        # Re-process identical content (no file change needed)
        await self.db.process_file(file_path)

        # Get new chunks
        new_chunks = self._get_chunks_for_file(str(file_path))

        # Should have same number of chunks
        assert len(new_chunks) == len(original_chunks)

        # Content should be identical
        for orig, new in zip(original_chunks, new_chunks):
            assert orig.get("content") == new.get("content"), (
                "Chunk content should be preserved"
            )
            assert orig.get("chunk_index") == new.get("chunk_index"), (
                "Chunk index should be preserved"
            )

    @pytest.mark.asyncio
    async def test_chunk_replacement_modified_content(self):
        """Test that modified chunks are replaced."""
        file_path = self.temp_dir / "test_replace.py"
        original_content = """def function1():
    return "hello"

def function2():
    return "world"
"""

        modified_content = """def function1():
    return "hello modified"

def function2():
    return "world"

def function3():
    return "new function"
"""

        # Write and index original content
        file_path.write_text(original_content)
        await self.db.process_file(file_path)
        original_chunks = self._get_chunks_for_file(str(file_path))

        # Write and process modified content
        file_path.write_text(modified_content)
        await self.db.process_file(file_path)
        modified_chunks = self._get_chunks_for_file(str(file_path))

        # Should have more chunks (new function added)
        assert len(modified_chunks) >= len(original_chunks)

        # Check symbols directly (ChunkHound stores symbols, not content)
        symbols = [chunk.get("symbol", "") for chunk in modified_chunks]
        
        # Should have function3 symbol
        new_function_found = "function3" in symbols
        assert new_function_found, f"Should find function3 in symbols: {symbols}"
        
        # Verify through search (user-facing test)
        search_results, _ = self.db.search_regex("function3")
        search_found = any(str(file_path) in r.get('file_path', '') for r in search_results)
        assert search_found, "Should find function3 via search"

    @pytest.mark.asyncio
    async def test_chunk_removal_deleted_content(self):
        """Test that chunks are removed when content is deleted."""
        file_path = self.temp_dir / "test_removal.py"
        original_content = """def function1():
    return "hello"

def function2():
    return "world"

def function3():
    return "extra"
"""

        reduced_content = """def function1():
    return "hello"
"""

        # Write and index original content
        file_path.write_text(original_content)
        await self.db.process_file(file_path)
        original_chunks = self._get_chunks_for_file(str(file_path))

        # Write and process reduced content
        file_path.write_text(reduced_content)
        await self.db.process_file(file_path)
        reduced_chunks = self._get_chunks_for_file(str(file_path))

        # Should have fewer chunks
        assert len(reduced_chunks) < len(original_chunks)

        # Should not find deleted content
        for chunk in reduced_chunks:
            content = chunk.get("content", "")
            assert "function2" not in content, "Should not find deleted function2"
            assert "function3" not in content, "Should not find deleted function3"

    @pytest.mark.asyncio
    async def test_partial_content_modification(self):
        """Test partial content modifications."""
        file_path = self.temp_dir / "test_partial.py"
        original_content = generate_unique_content("original")
        modified_content = generate_unique_content("modified")

        # Write and index original
        file_path.write_text(original_content)
        await self.db.process_file(file_path)
        original_chunks = self._get_chunks_for_file(str(file_path))

        # Write and process modified
        file_path.write_text(modified_content)
        await self.db.process_file(file_path)
        modified_chunks = self._get_chunks_for_file(str(file_path))

        # Should have same structure but different content
        assert len(modified_chunks) >= len(original_chunks)

        # Check symbols directly (ChunkHound stores symbols, not content)
        symbols = [chunk.get("symbol", "") for chunk in modified_chunks]
        
        # Should have modified_function symbol
        modified_found = "modified_function" in symbols
        assert modified_found, f"Should find modified_function in symbols: {symbols}"
        
        # Verify through search (user-facing test)
        search_results, _ = self.db.search_regex("modified_function")
        search_found = any(str(file_path) in r.get('file_path', '') for r in search_results)
        assert search_found, "Should find modified_function via search"


class TestEmbeddingPreservation:
    """Test embedding preservation during re-indexing."""

    def setup_method(self):
        """Setup test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_embeddings.db"

        config = Config(
            database={"path": str(self.db_path), "provider": "duckdb"},
            embedding={"provider": "openai", "model": "text-embedding-3-small"},
        )

        self.embedding_manager = EmbeddingManager()
        self.db = create_database_with_dependencies(
            db_path=self.db_path,
            config=config.to_dict(),
            embedding_manager=self.embedding_manager,
        )

    def teardown_method(self):
        """Cleanup test database."""
        if hasattr(self, "db"):
            self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_chunks_for_file(self, file_path):
        """Helper to get chunks for a file using correct API."""
        file_record = self.db.get_file_by_path(str(file_path))
        if not file_record:
            return []
        return self.db.get_chunks_by_file_id(file_record['id'])

    @patch.object(EmbeddingManager, 'embed_texts')
    @pytest.mark.asyncio
    async def test_embedding_preservation_unchanged_chunks(self, mock_embed):
        """Test that embeddings are preserved for unchanged chunks."""
        # Mock embedding response
        mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        from chunkhound.embeddings import LocalEmbeddingResult
        mock_embed.return_value = LocalEmbeddingResult(
            embeddings=[mock_embedding],
            model="test-model",
            provider="test",
            dims=5,
            total_tokens=10
        )

        file_path = self.temp_dir / "test_embedding.py"
        content = generate_unique_content("embedding")

        # Write and index original (will generate embeddings)
        file_path.write_text(content)
        await self.db.process_file(file_path)

        # Verify embedding was generated
        assert mock_embed.call_count > 0, "Should have generated embeddings"
        initial_call_count = mock_embed.call_count

        # Re-process identical content (should not generate new embeddings)
        await self.db.process_file(file_path)

        # Embedding count should not increase for identical content
        assert mock_embed.call_count == initial_call_count, (
            "Should not regenerate embeddings for identical content"
        )

    @patch.object(EmbeddingManager, 'embed_texts')
    @pytest.mark.asyncio
    async def test_embedding_regeneration_modified_chunks(self, mock_embed):
        """Test that embeddings are regenerated for modified chunks."""
        # Mock embedding response
        mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        from chunkhound.embeddings import LocalEmbeddingResult
        mock_embed.return_value = LocalEmbeddingResult(
            embeddings=[mock_embedding],
            model="test-model",
            provider="test",
            dims=5,
            total_tokens=10
        )

        file_path = self.temp_dir / "test_regen.py"
        original_content = generate_unique_content("original")
        modified_content = generate_unique_content("modified")

        # Write and index original
        file_path.write_text(original_content)
        await self.db.process_file(file_path)
        original_call_count = mock_embed.call_count

        # Write and process modified content
        file_path.write_text(modified_content)
        await self.db.process_file(file_path)

        # Should generate new embeddings for modified content
        assert mock_embed.call_count > original_call_count, (
            "Should regenerate embeddings for modified content"
        )

    @pytest.mark.asyncio
    async def test_embedding_consistency_after_update(self):
        """Test embedding consistency after file updates."""
        file_path = self.temp_dir / "test_consistency.py"
        content = generate_unique_content("consistency")

        # Index content multiple times
        for i in range(3):
            file_path.write_text(content)
            await self.db.process_file(file_path)

        # Get chunks and verify they have embeddings
        chunks = self._get_chunks_for_file(str(file_path))
        assert len(chunks) > 0, "Should have chunks"

        # Note: In real implementation, we'd check embedding vectors here
        # For now, just verify chunks exist and are consistent


class TestTransactionHandling:
    """Test transaction handling during re-indexing."""

    def setup_method(self):
        """Setup test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_transactions.db"

        config = Config(
            database={"path": str(self.db_path), "provider": "duckdb"},
            embedding={"provider": "openai", "model": "text-embedding-3-small"},
        )

        self.embedding_manager = EmbeddingManager()
        self.db = create_database_with_dependencies(
            db_path=self.db_path,
            config=config.to_dict(),
            embedding_manager=self.embedding_manager,
        )

    def teardown_method(self):
        """Cleanup test database."""
        if hasattr(self, "db"):
            self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_chunks_for_file(self, file_path):
        """Helper to get chunks for a file using correct API."""
        file_record = self.db.get_file_by_path(str(file_path))
        if not file_record:
            return []
        return self.db.get_chunks_by_file_id(file_record['id'])

    @pytest.mark.asyncio
    async def test_atomic_file_processing(self):
        """Test that file processing is atomic."""
        file_path = self.temp_dir / "test_atomic.py"
        content = generate_unique_content("atomic")

        # Write and process file
        file_path.write_text(content)
        await self.db.process_file(file_path)

        # Verify file was processed completely
        chunks = self._get_chunks_for_file(str(file_path))
        assert len(chunks) > 0, "File should be processed atomically"

        # Verify we can search for the content
        results, _ = self.db.search_regex("atomic_function")
        assert len(results) > 0, "Should find indexed content"

    @pytest.mark.asyncio
    async def test_rollback_on_processing_error(self):
        """Test rollback behavior on processing errors."""
        file_path = self.temp_dir / "test_rollback.py"
        content = generate_unique_content("rollback")

        # Write file first
        file_path.write_text(content)
        
        # For this test, we'll simulate the error at the Database level
        # rather than mocking process_file directly, since it could 
        # interfere with the setup/teardown
        with patch.object(self.db, '_indexing_coordinator') as mock_coordinator:
            mock_coordinator.process_file.side_effect = Exception("Processing failed")
            
            # Should raise exception
            with pytest.raises(Exception, match="Processing failed"):
                await self.db.process_file(file_path)

    @pytest.mark.asyncio
    async def test_concurrent_processing_safety(self):
        """Test safety of concurrent processing operations."""
        file_paths = [
            self.temp_dir / f"test_concurrent_{i}.py" 
            for i in range(5)
        ]

        # Create and process files concurrently
        tasks = []
        for i, file_path in enumerate(file_paths):
            content = generate_unique_content(f"concurrent_{i}")
            file_path.write_text(content)
            task = self.db.process_file(file_path)
            tasks.append(task)

        # Wait for all processing to complete
        await asyncio.gather(*tasks)

        # Verify all files were processed
        for i, file_path in enumerate(file_paths):
            chunks = self._get_chunks_for_file(str(file_path))
            assert len(chunks) > 0, f"File {i} should be processed"

    @pytest.mark.asyncio
    async def test_database_consistency_after_updates(self):
        """Test database consistency after multiple updates."""
        file_path = self.temp_dir / "test_consistency.py"
        contents = [
            generate_unique_content(f"version_{i}") 
            for i in range(5)
        ]

        # Process multiple versions sequentially
        for content in contents:
            file_path.write_text(content)
            await self.db.process_file(file_path)

        # Verify final state is consistent
        final_chunks = self._get_chunks_for_file(str(file_path))
        assert len(final_chunks) > 0, "Should have final chunks"

        # Should contain content from final version only
        final_content_found = False
        for chunk in final_chunks:
            if "version_4_function" in chunk.get("content", ""):
                final_content_found = True
        assert final_content_found, "Should contain final version content"


class TestIndexingCoordinatorOperations:
    """Test IndexingCoordinator integration operations."""

    def setup_method(self):
        """Setup test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_coordinator.db"

        config = Config(
            database={"path": str(self.db_path), "provider": "duckdb"},
            embedding={"provider": "openai", "model": "text-embedding-3-small"},
        )

        self.embedding_manager = EmbeddingManager()
        self.db = create_database_with_dependencies(
            db_path=self.db_path,
            config=config.to_dict(),
            embedding_manager=self.embedding_manager,
        )

    def teardown_method(self):
        """Cleanup test database."""
        if hasattr(self, "db"):
            self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_chunks_for_file(self, file_path):
        """Helper to get chunks for a file using correct API."""
        file_record = self.db.get_file_by_path(str(file_path))
        if not file_record:
            return []
        return self.db.get_chunks_by_file_id(file_record['id'])

    @pytest.mark.asyncio
    async def test_process_file_operation(self):
        """Test IndexingCoordinator.process_file operation."""
        file_path = self.temp_dir / "test_process.py"
        content = generate_unique_content("process")

        # Write and process file (IndexingCoordinator handles this)
        file_path.write_text(content)
        await self.db.process_file(file_path)

        # Verify file was processed
        chunks = self._get_chunks_for_file(str(file_path))
        assert len(chunks) > 0, "File should be processed"

    @pytest.mark.asyncio
    async def test_remove_file_operation(self):
        """Test IndexingCoordinator.remove_file operation."""
        file_path = self.temp_dir / "test_remove.py"
        content = generate_unique_content("remove")

        # First, write and process file
        file_path.write_text(content)
        await self.db.process_file(file_path)

        # Verify file exists
        chunks_before = self._get_chunks_for_file(str(file_path))
        assert len(chunks_before) > 0, "File should exist before removal"

        # Remove file from database
        self.db.delete_file_completely(str(file_path))

        # Verify file was removed
        chunks_after = self._get_chunks_for_file(str(file_path))
        assert len(chunks_after) == 0, "File should be removed"

    @pytest.mark.asyncio
    async def test_batch_file_operations(self):
        """Test batch file operations."""
        file_paths = [
            self.temp_dir / f"test_batch_{i}.py" 
            for i in range(10)
        ]
        contents = [generate_unique_content(f"batch_{i}") for i in range(10)]

        # Process files in batch
        for file_path, content in zip(file_paths, contents):
            file_path.write_text(content)
            await self.db.process_file(file_path)

        # Verify all files were processed
        for i, file_path in enumerate(file_paths):
            chunks = self._get_chunks_for_file(str(file_path))
            assert len(chunks) > 0, f"Batch file {i} should be processed"

    @pytest.mark.asyncio
    async def test_file_locking_prevention(self):
        """Test file locking prevention during operations."""
        file_path = self.temp_dir / "test_locking.py"
        
        # Simulate rapid operations that might cause locking issues
        operations = [
            (generate_unique_content("op1"), "process"),
            (generate_unique_content("op2"), "process"),
            (None, "remove"),
            (generate_unique_content("op3"), "process"),
        ]

        for content, operation in operations:
            if operation == "process":
                file_path.write_text(content)
                await self.db.process_file(file_path)
            elif operation == "remove":
                self.db.delete_file_completely(str(file_path))

        # Final verification
        final_chunks = self._get_chunks_for_file(str(file_path))
        assert len(final_chunks) > 0, "Final operation should succeed"


class TestSmartDiffingFunctionality:
    """Test smart diffing and incremental updates."""

    def setup_method(self):
        """Setup test database."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_diffing.db"

        config = Config(
            database={"path": str(self.db_path), "provider": "duckdb"},
            embedding={"provider": "openai", "model": "text-embedding-3-small"},
        )

        self.embedding_manager = EmbeddingManager()
        self.db = create_database_with_dependencies(
            db_path=self.db_path,
            config=config.to_dict(),
            embedding_manager=self.embedding_manager,
        )

    def teardown_method(self):
        """Cleanup test database."""
        if hasattr(self, "db"):
            self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_chunks_for_file(self, file_path):
        """Helper to get chunks for a file using correct API."""
        file_record = self.db.get_file_by_path(str(file_path))
        if not file_record:
            return []
        return self.db.get_chunks_by_file_id(file_record['id'])

    @pytest.mark.asyncio
    async def test_smart_diff_detection(self):
        """Test smart diff detection for minimal changes."""
        file_path = self.temp_dir / "test_diff.py"
        original_content = generate_unique_content("original")
        modified_content = generate_unique_content("modified")

        # Write and process original
        file_path.write_text(original_content)
        await self.db.process_file(file_path)
        original_chunks = self._get_chunks_for_file(str(file_path))

        # Write and process modified
        file_path.write_text(modified_content)
        await self.db.process_file(file_path)
        modified_chunks = self._get_chunks_for_file(str(file_path))

        # Should detect differences efficiently
        assert len(modified_chunks) >= len(original_chunks)

        # Check symbols directly (ChunkHound stores symbols, not content)
        symbols = [chunk.get("symbol", "") for chunk in modified_chunks]
        
        # Should have modified_function symbol
        found_modified = "modified_function" in symbols
        assert found_modified, f"Should find modified_function in symbols: {symbols}"
        
        # Verify through search (user-facing test)
        search_results, _ = self.db.search_regex("modified_function")
        search_found = any(str(file_path) in r.get('file_path', '') for r in search_results)
        assert search_found, "Should find modified_function via search"

    @pytest.mark.asyncio
    async def test_content_similarity_detection(self):
        """Test content similarity detection."""
        file_path = self.temp_dir / "test_similarity.py"
        version1 = generate_unique_content("v1")
        version2 = generate_unique_content("v2")

        # Process both versions
        file_path.write_text(version1)
        await self.db.process_file(file_path)
        
        file_path.write_text(version2)
        await self.db.process_file(file_path)

        # Should have content from version2
        chunks = self._get_chunks_for_file(str(file_path))
        found_v2 = False
        for chunk in chunks:
            if "v2_function" in chunk.get("content", ""):
                found_v2 = True
        assert found_v2, "Should have latest version content"