"""ChunkHound test package."""

__version__ = "0.1.0"

# Test configuration and utilities
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing."""
    return '''
def hello_world():
    """Print hello world."""
    print("Hello, World!")

class Calculator:
    """Simple calculator class."""
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def multiply(self, x: float, y: float) -> float:
        """Multiply two numbers."""
        return x * y

# Global variable
PI = 3.14159
'''


@pytest.fixture
def test_db_path(temp_dir: Path) -> Path:
    """Create a test database path."""
    return temp_dir / "test.duckdb"


# Test utilities
def create_test_file(directory: Path, filename: str, content: str) -> Path:
    """Create a test file with given content."""
    file_path = directory / filename
    file_path.write_text(content)
    return file_path