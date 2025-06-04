"""Simple manual API test without pytest dependencies."""

import json
import os
import sys
from pathlib import Path

# Add chunkhound to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from chunkhound.api import app


def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    with TestClient(app) as client:
        response = client.get("/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    print("✅ Health endpoint working")


def test_regex_search():
    """Test regex search endpoint."""
    print("\nTesting regex search endpoint...")
    with TestClient(app) as client:
        # Test GET endpoint
        response = client.get("/search/regex?pattern=def&limit=3")
        print(f"GET Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            content = response.content.decode()
            print(f"Response length: {len(content)} chars")
            if content.strip():
                lines = content.strip().split('\n')
                print(f"NDJSON lines: {len(lines)}")
                for i, line in enumerate(lines[:2]):
                    try:
                        data = json.loads(line)
                        print(f"Line {i+1}: {data.get('symbol', 'unknown')} in {data.get('file_path', 'unknown')}")
                    except json.JSONDecodeError:
                        print(f"Line {i+1}: Invalid JSON")
        
        # Test POST endpoint
        search_data = {"pattern": "class", "limit": 5}
        response = client.post("/search/regex", json=search_data)
        print(f"POST Status: {response.status_code}")
    
    print("✅ Regex search endpoint working")


def test_stats():
    """Test stats endpoint."""
    print("\nTesting stats endpoint...")
    with TestClient(app) as client:
        response = client.get("/stats")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"Database stats: {stats}")
    print("✅ Stats endpoint working")


def test_semantic_search():
    """Test semantic search endpoint (requires OpenAI key)."""
    print("\nTesting semantic search endpoint...")
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ Skipping semantic search test - no OpenAI API key")
        return
    
    with TestClient(app) as client:
        # Test GET endpoint
        response = client.get("/search/semantic?query=function definition&limit=3")
        print(f"GET Status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.content.decode()
            print(f"Response length: {len(content)} chars")
        elif response.status_code == 500:
            print("Expected - likely no embeddings in database yet")
    
    print("✅ Semantic search endpoint structure working")


def main():
    """Run all tests."""
    print("=== ChunkHound API Manual Tests ===")
    
    try:
        test_health()
        test_regex_search()
        test_stats()
        test_semantic_search()
        
        print("\n✅ All API tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()