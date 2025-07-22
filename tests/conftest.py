"""
Pytest configuration and fixtures for ChunkHound tests.
"""

import os
import tempfile
import pytest
from pathlib import Path
import json


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
