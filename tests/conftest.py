"""
Pytest configuration and fixtures for ChunkHound tests.
"""

import asyncio
import os
import tempfile
import pytest
from pathlib import Path
import json


@pytest.fixture
def event_loop():
    """
    Custom event loop fixture that ensures proper cleanup of async resources.
    
    This fixture helps prevent PytestUnraisableExceptionWarning by ensuring
    all pending tasks are properly cancelled before closing the event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        yield loop
    finally:
        # Ensure all pending tasks are cancelled
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        
        if pending_tasks:
            # Cancel all pending tasks
            for task in pending_tasks:
                task.cancel()
            
            # Wait for cancelled tasks to finish
            if pending_tasks:
                loop.run_until_complete(
                    asyncio.gather(*pending_tasks, return_exceptions=True)
                )
        
        # Close the loop properly
        try:
            loop.close()
        except RuntimeError:
            # Loop might already be closed
            pass


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    project_dir = temp_dir / "project"
    project_dir.mkdir()

    yield project_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_db_path(temp_project_dir):
    """Create a temporary database path."""
    return temp_project_dir / "test.db"


@pytest.fixture
def sample_local_config(temp_project_dir, temp_db_path):
    """Create a sample .chunkhound.json file."""
    local_config_path = temp_project_dir / ".chunkhound.json"
    local_config_content = {
        "database": {"path": str(temp_db_path)},
        "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
        "indexing": {"exclude": ["*.log", "node_modules/"]},
    }

    with open(local_config_path, "w") as f:
        json.dump(local_config_content, f)

    return local_config_path


@pytest.fixture
def clean_environment():
    """Clean up ChunkHound environment variables before and after tests."""
    # Store original values
    original_env = {}
    for key in list(os.environ.keys()):
        if key.startswith("CHUNKHOUND_"):
            original_env[key] = os.environ[key]
            del os.environ[key]

    yield

    # Restore original values
    for key in list(os.environ.keys()):
        if key.startswith("CHUNKHOUND_"):
            del os.environ[key]

    for key, value in original_env.items():
        os.environ[key] = value


@pytest.fixture
def mock_embedding_manager():
    """Create a mock embedding manager for testing."""
    from unittest.mock import Mock

    manager = Mock()
    manager.list_providers.return_value = ["openai"]
    manager.get_provider.return_value = Mock(
        name="openai", model="text-embedding-3-small"
    )

    return manager


@pytest.fixture(scope="session")
async def rerank_server():
    """
    Session-scoped fixture to manage mock reranking server for tests.
    
    This fixture automatically starts a mock reranking server if:
    1. No external reranking server is already running
    2. Tests that need reranking are being executed
    
    The server is automatically stopped at the end of the test session.
    """
    from tests.fixtures.rerank_server_manager import ensure_rerank_server_running
    
    # Check if we need a rerank server (only if running reranking tests)
    # This is determined by checking if any test uses the reranking fixtures
    manager = await ensure_rerank_server_running(start_if_needed=True)
    
    if manager:
        # We started a mock server, need to clean it up
        yield manager
        await manager.stop()
    else:
        # External server is running or not needed
        yield None


@pytest.fixture
async def ensure_rerank_server(rerank_server):
    """
    Test-scoped fixture that ensures reranking server is available.
    
    Use this fixture in tests that require reranking functionality.
    It will either use an existing external server or the mock server
    started by the session fixture.
    """
    from tests.fixtures.rerank_server_manager import RerankServerManager
    
    # Check if server is running
    manager = RerankServerManager()
    if await manager.is_running():
        return manager.base_url
    
    # If not, the session fixture should have started it
    if rerank_server:
        return rerank_server.base_url
    
    # No server available
    pytest.skip("No reranking server available for testing")
