"""API integration tests for ChunkHound FastAPI server."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from chunkhound.api import app
from chunkhound.database import Database
from chunkhound.embeddings import EmbeddingManager, create_openai_provider


@pytest.fixture
def test_db_path():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = Path(f.name)
    
    yield db_path
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def setup_test_data(test_db_path):
    """Set up test database with sample data."""
    # Create database and add test data
    db = Database(test_db_path)
    db.connect()
    db.create_tables()
    
    # Add a test file
    file_id = db.insert_file("/test/example.py", "python")
    
    # Add test chunks
    chunk_data = [
        {
            "file_id": file_id,
            "symbol": "test_function",
            "start_line": 1,
            "end_line": 5,
            "code": 'def test_function():\n    """Test function."""\n    return "hello"',
            "chunk_type": "function"
        },
        {
            "file_id": file_id,
            "symbol": "TestClass",
            "start_line": 7,
            "end_line": 12,
            "code": 'class TestClass:\n    """Test class."""\n    def method(self):\n        return 42',
            "chunk_type": "class"
        }
    ]
    
    chunk_ids = []
    for chunk in chunk_data:
        chunk_id = db.insert_chunk(**chunk)
        chunk_ids.append(chunk_id)
    
    # Add mock embeddings (using dummy vectors)
    dummy_vector = [0.1] * 1536  # OpenAI embedding dimension
    
    for chunk_id in chunk_ids:
        db.insert_embedding(
            chunk_id=chunk_id,
            provider="openai",
            model="text-embedding-3-small",
            dims=1536,
            vector=dummy_vector
        )
    
    db.close()
    return test_db_path, chunk_ids


def test_health_endpoint():
    """Test health check endpoint."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


def test_regex_search_get():
    """Test GET regex search endpoint."""
    with TestClient(app) as client:
        # Test basic regex search
        response = client.get("/search/regex?pattern=test&limit=5")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"


def test_regex_search_post():
    """Test POST regex search endpoint."""
    with TestClient(app) as client:
        search_data = {
            "pattern": "def.*test",
            "limit": 10
        }
        response = client.post("/search/regex", json=search_data)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"


def test_semantic_search_get():
    """Test GET semantic search endpoint."""
    # Skip if no OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not available")
    
    with TestClient(app) as client:
        response = client.get("/search/semantic?query=test function&limit=5")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"


def test_semantic_search_post():
    """Test POST semantic search endpoint."""
    # Skip if no OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not available")
    
    with TestClient(app) as client:
        search_data = {
            "query": "test function",
            "limit": 10,
            "provider": "openai",
            "model": "text-embedding-3-small"
        }
        response = client.post("/search/semantic", json=search_data)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"


def test_stats_endpoint():
    """Test database stats endpoint."""
    with TestClient(app) as client:
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "chunks" in data
        assert "embeddings" in data


def test_ndjson_format():
    """Test that responses are valid NDJSON."""
    with TestClient(app) as client:
        response = client.get("/search/regex?pattern=.*&limit=2")
        assert response.status_code == 200
        
        # Check NDJSON format
        content = response.content.decode()
        if content.strip():  # Only test if there's content
            lines = content.strip().split("\n")
            for line in lines:
                # Each line should be valid JSON
                data = json.loads(line)
                assert isinstance(data, dict)


def test_invalid_requests():
    """Test error handling for invalid requests."""
    with TestClient(app) as client:
        # Invalid regex pattern
        response = client.post("/search/regex", json={"pattern": "", "limit": 10})
        assert response.status_code == 422 or response.status_code == 500
        
        # Invalid limit
        response = client.get("/search/regex?pattern=test&limit=0")
        assert response.status_code == 422
        
        # Invalid semantic search
        response = client.post("/search/semantic", json={"query": "", "limit": 10})
        assert response.status_code == 422 or response.status_code == 500


@pytest.mark.asyncio
async def test_async_client():
    """Test API with async client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        
        # Test regex search
        response = await ac.get("/search/regex?pattern=test&limit=5")
        assert response.status_code == 200


def test_missing_endpoints():
    """Test that non-existent endpoints return 404."""
    with TestClient(app) as client:
        response = client.get("/nonexistent")
        assert response.status_code == 404
        
        response = client.post("/search/nonexistent", json={})
        assert response.status_code == 404


if __name__ == "__main__":
    # Run basic tests
    print("Testing ChunkHound API...")
    
    # Test health check
    with TestClient(app) as client:
        response = client.get("/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test regex search
        response = client.get("/search/regex?pattern=def&limit=3")
        print(f"Regex search: {response.status_code}")
        if response.status_code == 200:
            content = response.content.decode()
            print(f"Response length: {len(content)} characters")
        
    print("API tests completed!")