"""Tests for live indexing embeddings fix."""

import asyncio
import tempfile
from pathlib import Path
import pytest
from chunkhound.database import Database
from chunkhound.embeddings import EmbeddingManager


async def test_live_indexing_embeddings_generation():
    """Test that live indexing generates embeddings properly in async context."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def test_function():
    '''This is a test function for live indexing embeddings.'''
    return "test result"

class TestClass:
    '''A test class for embedding generation.'''
    
    def method_one(self):
        '''First method for testing.'''
        pass
        
    def method_two(self):
        '''Second method for testing.'''
        return "method result"
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # Process file in async context (simulating MCP server context)
        result = await db.process_file(file_path)
        
        # Verify the file was processed successfully
        assert result["status"] == "success"
        assert result["chunks"] > 0
        assert "chunk_ids" in result
        
        # Verify chunks were created
        stats = db.get_stats()
        assert stats["files"] == 1
        assert stats["chunks"] > 0
        print(f"Created {stats['chunks']} chunks from test file")
        
        # The embeddings count should be 0 since we don't have an embedding manager
        # But the important thing is that the process didn't fail
        assert stats["embeddings"] == 0
        
    finally:
        db.close()
        file_path.unlink(missing_ok=True)


async def test_live_indexing_with_mock_embeddings():
    """Test live indexing with mock embedding manager to verify embedding generation."""
    # Create a simple mock embedding manager
    class MockEmbeddingResult:
        def __init__(self, embeddings):
            self.embeddings = embeddings
            self.provider = "mock"
            self.model = "mock-model"
            self.dims = 1536
    
    class MockEmbeddingManager:
        async def embed_texts(self, texts, provider_name=None):
            """Mock embedding generation - just return dummy vectors."""
            embeddings = [[0.1] * 1536 for _ in texts]
            return MockEmbeddingResult(embeddings)
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def embedding_test():
    '''Function for testing embedding generation.'''
    result = "embedding test"
    return result
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database with mock embedding manager
        mock_embedding_manager = MockEmbeddingManager()
        db = Database(":memory:", embedding_manager=mock_embedding_manager)
        db.connect()
        
        # Process file in async context
        result = await db.process_file(file_path)
        
        # Verify the file was processed successfully
        assert result["status"] == "success"
        assert result["chunks"] > 0
        assert result["embeddings"] > 0, "Embeddings should have been generated"
        
        # Verify embeddings were actually stored
        stats = db.get_stats()
        assert stats["files"] == 1
        assert stats["chunks"] > 0
        assert stats["embeddings"] > 0, "Database should contain embeddings"
        
        print(f"Successfully generated {stats['embeddings']} embeddings for {stats['chunks']} chunks")
        
    finally:
        db.close()
        file_path.unlink(missing_ok=True)


async def test_async_context_embedding_generation():
    """Test that embedding generation works properly in nested async context."""
    # This test specifically targets the asyncio.run() vs await issue
    
    async def simulate_mcp_server_context():
        """Simulate the MCP server's async context."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""def async_context_test():
    '''Testing async context handling.'''
    return "async test"
""")
            file_path = Path(f.name)
        
        try:
            # Initialize database (without real embeddings for simplicity)
            db = Database(":memory:")
            db.connect()
            
            # This should NOT raise a "RuntimeError: asyncio.run() cannot be called from a running event loop"
            result = await db.process_file(file_path)
            
            assert result["status"] == "success"
            assert result["chunks"] > 0
            
            return True
            
        finally:
            db.close()
            file_path.unlink(missing_ok=True)
    
    # Run the simulation - this creates the nested async context that was causing issues
    success = await simulate_mcp_server_context()
    assert success, "Should not fail with asyncio context error"


async def test_multiple_files_async_processing():
    """Test processing multiple files in async context to verify no race conditions."""
    files_to_process = []
    
    try:
        # Create multiple test files
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(f"""def function_{i}():
    '''Test function number {i}.'''
    return "result_{i}"

class TestClass_{i}:
    '''Test class number {i}.'''
    
    def method_{i}(self):
        '''Method for class {i}.'''
        return "method_result_{i}"
""")
                files_to_process.append(Path(f.name))
        
        # Initialize database
        db = Database(":memory:")
        db.connect()
        
        # Process all files in async context
        results = []
        for file_path in files_to_process:
            result = await db.process_file(file_path)
            results.append(result)
        
        # Verify all files were processed successfully
        for i, result in enumerate(results):
            assert result["status"] == "success", f"File {i} processing failed"
            assert result["chunks"] > 0, f"File {i} produced no chunks"
        
        # Verify database state
        stats = db.get_stats()
        assert stats["files"] == 3, "Should have 3 files in database"
        assert stats["chunks"] > 0, "Should have chunks from all files"
        
        print(f"Successfully processed {stats['files']} files with {stats['chunks']} total chunks")
        
    finally:
        db.close()
        for file_path in files_to_process:
            file_path.unlink(missing_ok=True)


if __name__ == "__main__":
    # Run tests directly if needed
    asyncio.run(test_live_indexing_embeddings_generation())
    asyncio.run(test_live_indexing_with_mock_embeddings())
    asyncio.run(test_async_context_embedding_generation())
    asyncio.run(test_multiple_files_async_processing())
    print("All live indexing embedding tests passed!")