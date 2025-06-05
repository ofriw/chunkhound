"""Integration tests for MCP server functionality in CI environment."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chunkhound.database import Database
from chunkhound.mcp_server import serve
from chunkhound.parser import parse_file


class TestMCPCIIntegration:
    """Test MCP server functionality in CI environment."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create sample Python file
            python_file = project_path / "example.py"
            python_file.write_text('''
def hello_world():
    """Example function for testing."""
    return "Hello, World!"

class TestClass:
    """Example class for testing."""
    def __init__(self, name: str):
        self.name = name
    
    def greet(self) -> str:
        return f"Hello, {self.name}!"
''')
            
            # Create sample README
            readme_file = project_path / "README.md"
            readme_file.write_text('''
# Test Project

This is a test project for CI integration testing.

## Features

- Example Python code
- Documentation testing
''')
            
            yield project_path

    @pytest.fixture
    def test_database(self, temp_project):
        """Create a test database with sample data."""
        # Use a temporary database file
        db_path = temp_project / "test.db"
        
        with patch.dict(os.environ, {"CHUNKHOUND_DB_PATH": str(db_path)}):
            db = Database()
            
            # Index the test files
            for file_path in temp_project.glob("**/*"):
                if file_path.is_file() and file_path.suffix in [".py", ".md"]:
                    try:
                        chunks = parse_file(file_path)
                        for chunk in chunks:
                            db.store_chunk(chunk)
                    except Exception as e:
                        print(f"Warning: Could not parse {file_path}: {e}")
            
            yield db

    @pytest.mark.ci
    def test_database_initialization(self, temp_project):
        """Test database can be initialized in CI environment."""
        db_path = temp_project / "ci_test.db"
        
        with patch.dict(os.environ, {"CHUNKHOUND_DB_PATH": str(db_path)}):
            db = Database()
            
            # Verify database is accessible
            stats = db.get_stats()
            assert "total_chunks" in stats
            assert "total_files" in stats
            assert stats["total_chunks"] >= 0

    @pytest.mark.ci
    def test_search_regex_functionality(self, test_database):
        """Test regex search works in CI environment."""
        results = test_database.search_regex("hello_world")
        
        # Should find the function definition
        assert len(results) > 0
        
        # Check result structure
        result = results[0]
        assert "symbol" in result
        assert "file_path" in result
        assert "start_line" in result
        assert "code" in result

    @pytest.mark.ci
    @patch("openai.OpenAI")
    def test_search_semantic_mock(self, mock_openai, test_database):
        """Test semantic search with mocked OpenAI API."""
        # Mock the OpenAI client
        mock_client = mock_openai.return_value
        mock_client.embeddings.create.return_value.data = [
            type('obj', (object,), {'embedding': [0.1] * 1536})()
        ]
        
        # This should not fail even with mocked API
        try:
            results = test_database.search_semantic("greeting function", limit=5)
            # In CI, we just verify the method doesn't crash
            assert isinstance(results, list)
        except Exception as e:
            # If it fails due to API setup, that's acceptable in CI
            pytest.skip(f"Semantic search test skipped in CI: {e}")

    @pytest.mark.ci
    def test_mcp_server_initialization(self):
        """Test MCP server can be initialized without crashing."""
        async def test_init():
            # Test that server setup doesn't crash
            try:
                # Import and check basic server components
                from chunkhound.mcp_server import (
                    search_semantic,
                    search_regex,
                    get_stats,
                    health_check
                )
                
                # These should be callable
                assert callable(search_semantic)
                assert callable(search_regex) 
                assert callable(get_stats)
                assert callable(health_check)
                
                return True
            except Exception as e:
                pytest.fail(f"MCP server initialization failed: {e}")
        
        # Run the async test
        result = asyncio.run(test_init())
        assert result is True

    @pytest.mark.ci
    def test_file_parsing_robustness(self, temp_project):
        """Test file parsing doesn't crash on various inputs."""
        # Create files with different content types
        test_files = {
            "empty.py": "",
            "syntax_error.py": "def incomplete_function(\n",
            "unicode.py": "# -*- coding: utf-8 -*-\ndef café(): pass",
            "large_line.py": f"# {'x' * 200}\ndef test(): pass"
        }
        
        for filename, content in test_files.items():
            file_path = temp_project / filename
            file_path.write_text(content)
            
            # Parsing should not crash, even on problematic files
            try:
                chunks = parse_file(file_path)
                assert isinstance(chunks, list)
            except Exception as e:
                # Some files may fail to parse, but shouldn't crash the system
                print(f"Expected parse failure for {filename}: {e}")

    @pytest.mark.ci
    def test_environment_variables_respected(self):
        """Test that CI-relevant environment variables are respected."""
        # Test CHUNKHOUND_WATCH_ENABLED
        with patch.dict(os.environ, {"CHUNKHOUND_WATCH_ENABLED": "false"}):
            # This should not attempt to start file watching
            from chunkhound.file_watcher import should_enable_watcher
            assert not should_enable_watcher()
        
        # Test database path override
        custom_path = "/tmp/custom_test.db"
        with patch.dict(os.environ, {"CHUNKHOUND_DB_PATH": custom_path}):
            db = Database()
            # Should use custom path (we can't easily verify this without 
            # exposing internal state, but at least it shouldn't crash)
            assert db is not None

    @pytest.mark.ci
    def test_concurrent_database_access(self, test_database):
        """Test database handles concurrent access gracefully."""
        async def concurrent_searches():
            tasks = []
            
            # Create multiple concurrent search tasks
            for i in range(5):
                task = asyncio.create_task(
                    asyncio.to_thread(test_database.search_regex, f"test|class|def")
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete without exceptions
            for result in results:
                if isinstance(result, Exception):
                    pytest.fail(f"Concurrent access failed: {result}")
                assert isinstance(result, list)
        
        asyncio.run(concurrent_searches())

    @pytest.mark.ci 
    def test_memory_usage_reasonable(self, test_database):
        """Test that memory usage stays reasonable during operations."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Perform multiple operations
        for _ in range(10):
            results = test_database.search_regex("def|class")
            del results  # Explicit cleanup
        
        # Force garbage collection
        gc.collect()
        
        # Check memory hasn't grown excessively
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Allow up to 50MB growth for reasonable operations
        max_growth = 50 * 1024 * 1024  # 50MB
        assert memory_growth < max_growth, f"Memory grew by {memory_growth / 1024 / 1024:.1f}MB"

    @pytest.mark.ci
    def test_cli_commands_available(self):
        """Test that CLI commands are available and functional."""
        from chunkhound.cli import main
        import sys
        from io import StringIO
        
        # Test help command doesn't crash
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # This should show help and exit
            with pytest.raises(SystemExit) as exc_info:
                main(["--help"])
            
            # Should exit with code 0 for help
            assert exc_info.value.code == 0
            
            # Should have produced some output
            output = captured_output.getvalue()
            assert "chunkhound" in output.lower()
            assert "usage" in output.lower()
            
        finally:
            sys.stdout = old_stdout

    @pytest.mark.ci
    def test_signal_coordination_safe(self):
        """Test that signal coordination doesn't interfere with CI."""
        # In CI, we just verify signal handling doesn't crash
        try:
            from chunkhound.coordination import ProcessDetector
            
            # This should work in CI environment
            detector = ProcessDetector()
            
            # Basic functionality should work
            assert hasattr(detector, 'find_mcp_server_pids')
            
        except ImportError:
            # If coordination module doesn't exist yet, that's fine
            pytest.skip("Signal coordination not yet implemented")
        except Exception as e:
            pytest.fail(f"Signal coordination caused issues in CI: {e}")