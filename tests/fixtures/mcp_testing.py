"""
Test fixtures for MCP server file watching functionality.
"""

import asyncio
import os
import subprocess
import tempfile
import time
import pytest
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
from unittest.mock import Mock, patch
from contextlib import asynccontextmanager

from chunkhound.core.config.config import Config
from chunkhound.database_factory import create_database_with_dependencies
from chunkhound.embeddings import EmbeddingManager


class MCPServerTestFixture:
    """Test fixture for MCP server with file watching capabilities."""

    def __init__(self, project_dir: Path, config: Config):
        self.project_dir = project_dir
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.db_path = Path(config.database.path)

    async def start_mcp_server(self, transport: str = "stdio") -> bool:
        """Start MCP server in background."""
        cmd = ["uv", "run", "chunkhound", "mcp", transport]

        env = os.environ.copy()
        env.update(
            {
                "CHUNKHOUND_DATABASE__PATH": str(self.db_path),
                "CHUNKHOUND_MCP_MODE": "1",
                "CHUNKHOUND_WATCH_ENABLED": "true",
                "CHUNKHOUND_WATCH_PATHS": str(self.project_dir),
                "CHUNKHOUND_DEBUG": "1",
            }
        )

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_dir,
            env=env,
        )

        # Wait for startup
        await asyncio.sleep(3)
        return self.process.poll() is None

    async def stop_mcp_server(self):
        """Stop MCP server gracefully."""
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_process()), timeout=5
                )
            except asyncio.TimeoutError:
                self.process.kill()
                await asyncio.create_task(self._wait_for_process())

    async def _wait_for_process(self):
        """Wait for process to exit."""
        while self.process and self.process.poll() is None:
            await asyncio.sleep(0.1)


class MockFileWatcher:
    """Mock file watcher for controlled testing."""

    def __init__(self):
        self.events: List[Dict] = []
        self.handlers = []
        self.started = False

    def add_handler(self, handler):
        """Add event handler."""
        self.handlers.append(handler)

    def start_watching(self):
        """Start watching (mock)."""
        self.started = True

    def stop_watching(self):
        """Stop watching (mock)."""
        self.started = False

    async def simulate_file_event(
        self, event_type: str, file_path: Path, delay: float = 0
    ):
        """Simulate a file system event."""
        if delay > 0:
            await asyncio.sleep(delay)

        event = {
            "event_type": event_type,
            "file_path": str(file_path),
            "timestamp": time.time(),
        }

        self.events.append(event)

        # Call handlers
        for handler in self.handlers:
            try:
                await handler.on_file_event(event_type, file_path)
            except Exception as e:
                print(f"Handler error: {e}")


@pytest.fixture
async def temp_project_with_monitoring():
    """Create a temporary project with file monitoring setup."""
    temp_dir = Path(tempfile.mkdtemp())
    project_dir = temp_dir / "test_project"
    project_dir.mkdir(parents=True)

    # Create some initial test files
    (project_dir / "test.py").write_text("print('hello')")
    (project_dir / "test.js").write_text("console.log('hello');")

    db_path = project_dir / ".chunkhound" / "test.db"
    db_path.parent.mkdir(exist_ok=True)

    # Create config
    config = Config(
        database={"path": str(db_path), "provider": "duckdb"},
        embedding={"provider": "openai", "model": "text-embedding-3-small"},
        indexing={
            "watch": True,
            "debounce_ms": 100,
            "include": ["*.py", "*.js"],
            "exclude": ["*.log"],
        },
    )

    fixture = MCPServerTestFixture(project_dir, config)

    yield fixture

    # Cleanup
    await fixture.stop_mcp_server()
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def database_with_change_tracking(temp_project_with_monitoring):
    """Database configured to track file change operations."""
    fixture = temp_project_with_monitoring

    # Create database with dependencies
    embedding_manager = EmbeddingManager()
    db = create_database_with_dependencies(
        db_path=fixture.db_path,
        config=fixture.config.to_dict(),
        embedding_manager=embedding_manager,
    )

    yield db

    db.close()


@pytest.fixture
def mock_file_watcher():
    """Controllable file watcher for testing."""
    return MockFileWatcher()


@asynccontextmanager
async def with_mcp_server(
    project_dir: Path, config: Config
) -> AsyncGenerator[MCPServerTestFixture, None]:
    """Context manager for MCP server testing."""
    fixture = MCPServerTestFixture(project_dir, config)

    try:
        started = await fixture.start_mcp_server()
        if not started:
            raise RuntimeError("Failed to start MCP server")
        yield fixture
    finally:
        await fixture.stop_mcp_server()


@pytest.fixture
async def mcp_server_with_watcher(temp_project_with_monitoring):
    """MCP server with file watcher in test mode."""
    fixture = temp_project_with_monitoring

    # Start server
    started = await fixture.start_mcp_server()
    if not started:
        pytest.skip("Failed to start MCP server for testing")

    yield fixture

    # Cleanup handled by temp_project_with_monitoring fixture


class FileOperationSimulator:
    """Simulate controlled file operations for testing."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.created_files: List[Path] = []

    def create_file(self, name: str, content: str) -> Path:
        """Create a test file."""
        file_path = self.project_dir / name
        file_path.write_text(content)
        self.created_files.append(file_path)
        return file_path

    def modify_file(self, file_path: Path, content: str):
        """Modify an existing file."""
        file_path.write_text(content)

    def delete_file(self, file_path: Path):
        """Delete a file."""
        if file_path.exists():
            file_path.unlink()
            if file_path in self.created_files:
                self.created_files.remove(file_path)

    def move_file(self, src: Path, dst: Path):
        """Move/rename a file."""
        src.rename(dst)
        if src in self.created_files:
            self.created_files.remove(src)
            self.created_files.append(dst)

    def cleanup(self):
        """Clean up all created files."""
        for file_path in self.created_files[:]:
            if file_path.exists():
                file_path.unlink()
        self.created_files.clear()


@pytest.fixture
def file_operations(temp_project_with_monitoring):
    """File operation simulator for testing."""
    fixture = temp_project_with_monitoring
    simulator = FileOperationSimulator(fixture.project_dir)

    yield simulator

    # Cleanup
    simulator.cleanup()
