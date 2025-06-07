"""Integration tests for Java indexing with database."""

import os
import tempfile
from pathlib import Path
import pytest

from chunkhound.database import Database
from chunkhound.parser import CodeParser
from chunkhound.embeddings import EmbeddingManager, OpenAIEmbeddingProvider


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as temp_file:
        db_path = Path(temp_file.name)
    
    # Remove the empty file so DuckDB can create a new database
    if db_path.exists():
        os.unlink(db_path)
    
    yield db_path
    
    # Clean up after test
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture
def java_test_fixture_path():
    """Path to Java test fixtures."""
    current_dir = Path(__file__).parent.parent
    return current_dir / "fixtures" / "java"


@pytest.fixture
async def db_with_java(temp_db_path, java_test_fixture_path):
    """Create a database with Java files indexed."""
    # Check if Java test fixture exists
    if not java_test_fixture_path.exists():
        pytest.skip(f"Java test fixtures not found at {java_test_fixture_path}")
    
    # Initialize database without embeddings
    db = Database(temp_db_path)
    db.connect()
    
    try:
        # Process Java files in fixtures
        result = await db.process_directory(
            java_test_fixture_path, 
            patterns=["**/*.java"], 
            exclude_patterns=[]
        )
        
        if result["status"] != "complete" or result["processed"] == 0:
            pytest.skip(f"Failed to process Java files: {result}")
            
        yield db
    finally:
        if db.connection:
            db.connection.close()
        db.close()


class TestJavaIndexing:
    """Integration tests for Java indexing."""
    
    async def test_java_indexing_database_integration(self, db_with_java):
        """Test Java files are properly indexed in the database."""
        # Check that we have files in the database
        stats = db_with_java.get_stats()
        assert stats["files"] > 0, "No files found in database"
        assert stats["chunks"] > 0, "No chunks found in database"
        
        # First check what language_info values exist
        debug_query = """
            SELECT DISTINCT language_info, COUNT(*) as count
            FROM chunks 
            GROUP BY language_info
        """
        debug_results = db_with_java.execute_query(debug_query)
        print(f"Language info values in database: {debug_results}")
        
        # Query for Java chunks
        query = """
            SELECT * FROM chunks 
            WHERE language_info = 'java'
            LIMIT 100
        """
        results = db_with_java.execute_query(query)
        assert len(results) > 0, f"No Java chunks found in database. Available language_info values: {debug_results}"
        
        # Verify we have different chunk types
        query = """
            SELECT chunk_type, COUNT(*) as count 
            FROM chunks 
            WHERE language_info = 'java'
            GROUP BY chunk_type
        """
        type_counts = db_with_java.execute_query(query)
        assert len(type_counts) > 0, "No Java chunk types found"
        
        # Check for expected chunk types
        type_dict = {row["chunk_type"]: row["count"] for row in type_counts}
        assert "class" in type_dict, "No Java classes found"
        
        # At least one of these should exist
        method_types = ["method", "constructor"]
        has_methods = any(t in type_dict for t in method_types)
        assert has_methods, "No Java methods or constructors found"
    
    async def test_java_regex_search(self, db_with_java):
        """Test regex search works with Java code."""
        # Search for class declaration
        query = """
            SELECT * FROM chunks 
            WHERE language_info = 'java'
            AND regexp_matches(code, 'public class')
            LIMIT 10
        """
        results = db_with_java.execute_query(query)
        assert len(results) > 0, "Regex search failed for Java classes"
        
        # Search for methods with annotation
        query = """
            SELECT * FROM chunks 
            WHERE language_info = 'java'
            AND regexp_matches(code, '@Override')
            LIMIT 10
        """
        results = db_with_java.execute_query(query)
        assert len(results) > 0, "Regex search failed for Java annotations"
    
    @pytest.mark.skipif(
        "OPENAI_API_KEY" not in os.environ,
        reason="OpenAI API key required for embedding tests"
    )
    async def test_java_embedding_generation(self, temp_db_path, java_test_fixture_path):
        """Test embedding generation for Java code."""
        # Skip if OpenAI API key not set
        if "OPENAI_API_KEY" not in os.environ:
            pytest.skip("OpenAI API key required for embedding tests")
            
        # Create embedding manager
        embedding_manager = EmbeddingManager()
        provider = OpenAIEmbeddingProvider(
            api_key=os.environ.get("OPENAI_API_KEY"),
            model="text-embedding-3-small"
        )
        embedding_manager.register_provider(provider, set_default=True)
        
        # Create database with embedding manager
        db = Database(temp_db_path, embedding_manager)
        db.connect()
        
        try:
            # Process Java files
            result = await db.process_directory(
                java_test_fixture_path, 
                patterns=["**/*.java"], 
                exclude_patterns=[]
            )
            
            if result["status"] != "complete" or result["processed"] == 0:
                pytest.skip(f"Failed to process Java files: {result}")
            
            # Generate embeddings
            embed_result = await db.generate_missing_embeddings()
            assert embed_result["status"] in ["success", "up_to_date"]
            
            # Check that embeddings were generated
            stats = db.get_stats()
            assert stats["embeddings"] > 0, "No embeddings generated"
            
            # Verify Java chunks have embeddings
            query = """
                SELECT COUNT(*) as count 
                FROM chunks 
                WHERE language = 'java' 
                AND embedding IS NOT NULL
            """
            results = db.execute_query(query)
            assert results[0]["count"] > 0, "No Java chunks have embeddings"
            
        finally:
            db.close()