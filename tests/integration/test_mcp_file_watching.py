"""
Integration tests for MCP server file watching functionality.

Tests the end-to-end flow of:
1. MCP server startup with file watcher initialization
2. File change detection and processing
3. Database updates and search verification
4. Configuration consistency between modes
"""

import asyncio
import os
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock

from chunkhound.core.config.config import Config
from tests.fixtures.mcp_testing import (
    temp_project_with_monitoring,
    mcp_server_with_watcher,
    database_with_change_tracking,
    file_operations,
    with_mcp_server,
)
from tests.utils.file_watching_helpers import (
    FileWatchingAssertions,
    generate_unique_content,
    wait_for_file_processing,
    wait_for_file_removal,
    DebugHelper,
)


class TestMCPServerFileWatchingIntegration:
    """Test MCP server with integrated file watching."""

    @pytest.mark.asyncio
    async def test_mcp_server_startup_with_file_watcher(
        self, temp_project_with_monitoring
    ):
        """Test MCP server initializes file watcher on startup."""
        fixture = temp_project_with_monitoring

        # Start server
        started = await fixture.start_mcp_server()

        try:
            assert started, "MCP server should start successfully"

            # Check that process is running
            assert fixture.process is not None
            assert fixture.process.poll() is None, (
                "MCP server process should be running"
            )

            # Give server time to initialize file watcher
            await asyncio.sleep(2)

            # Server should still be running (not crashed during file watcher init)
            assert fixture.process.poll() is None, (
                "MCP server should not crash during file watcher initialization"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_file_creation_detection_and_indexing(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test that newly created files are detected and indexed."""
        fixture = temp_project_with_monitoring

        # Start server with file watching
        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            # Give server time to initialize
            await asyncio.sleep(3)

            # Create unique test content
            unique_content = generate_unique_content("creation")
            test_file = file_operations.create_file("test_creation.py", unique_content)

            # Wait for file to be processed
            assertions = FileWatchingAssertions(fixture.db_path, timeout=15.0)

            # Check file is indexed
            file_indexed = await assertions.assert_file_indexed_within_timeout(
                test_file
            )

            # Check content is searchable
            content_searchable = (
                await assertions.assert_content_searchable_within_timeout(
                    "creation_function_"
                )
            )

            if not file_indexed or not content_searchable:
                # Debug information
                DebugHelper.print_database_state(fixture.db_path)
                DebugHelper.print_search_results(fixture.db_path, "creation_function_")

            assert file_indexed, f"File {test_file} should be indexed within timeout"
            assert content_searchable, (
                "File content should be searchable within timeout"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_file_modification_detection_and_reindexing(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test that file modifications are detected and re-indexed."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create initial file
            initial_content = generate_unique_content("initial")
            test_file = file_operations.create_file(
                "test_modification.py", initial_content
            )

            # Wait for initial indexing
            success = await wait_for_file_processing(
                test_file, "initial_function_", fixture.db_path
            )
            assert success, "Initial file should be indexed"

            # Modify file with new content
            modified_content = generate_unique_content("modified")
            file_operations.modify_file(test_file, modified_content)

            # Wait for re-indexing
            assertions = FileWatchingAssertions(fixture.db_path, timeout=15.0)

            # New content should be searchable
            new_content_found = (
                await assertions.assert_content_searchable_within_timeout(
                    "modified_function_"
                )
            )

            # Old content should eventually be gone (may take time due to chunk updates)
            old_content_gone = (
                await assertions.assert_content_not_searchable_within_timeout(
                    "initial_function_", timeout=20.0
                )
            )

            if not new_content_found:
                DebugHelper.print_database_state(fixture.db_path)
                DebugHelper.print_search_results(fixture.db_path, "modified_function_")

            assert new_content_found, "Modified content should be searchable"
            assert old_content_gone, "Original content should be removed from index"

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_file_deletion_detection_and_cleanup(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test that file deletions are detected and removed from index."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create file
            unique_content = generate_unique_content("deletion")
            test_file = file_operations.create_file("test_deletion.py", unique_content)

            # Wait for indexing
            success = await wait_for_file_processing(
                test_file, "deletion_function_", fixture.db_path
            )
            assert success, "File should be indexed before deletion"

            # Delete file
            file_operations.delete_file(test_file)

            # Wait for cleanup
            content_removed = await wait_for_file_removal(
                "deletion_function_", fixture.db_path, timeout=15.0
            )

            if not content_removed:
                DebugHelper.print_database_state(fixture.db_path)
                DebugHelper.print_search_results(fixture.db_path, "deletion_function_")

            assert content_removed, (
                "Content from deleted file should be removed from index"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_configuration_consistency_stdio_vs_http(
        self, temp_project_with_monitoring
    ):
        """Test configuration consistency between stdio and HTTP servers."""
        fixture = temp_project_with_monitoring

        # Test stdio server
        stdio_started = await fixture.start_mcp_server("stdio")
        if stdio_started:
            await asyncio.sleep(2)
            stdio_running = fixture.process.poll() is None
            await fixture.stop_mcp_server()
        else:
            stdio_running = False

        # Test HTTP server
        http_started = await fixture.start_mcp_server("http")
        if http_started:
            await asyncio.sleep(2)
            http_running = fixture.process.poll() is None
            await fixture.stop_mcp_server()
        else:
            http_running = False

        # Both should start successfully with same config
        assert stdio_running, (
            "stdio server should start and run with file watching config"
        )
        assert http_running, (
            "HTTP server should start and run with file watching config"
        )

    @pytest.mark.asyncio
    async def test_rapid_file_changes_handling(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of rapid successive file changes."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create file
            test_file = file_operations.create_file(
                "rapid_test.py", "# Initial content"
            )

            # Make rapid changes
            changes = []
            for i in range(5):
                change_content = generate_unique_content(f"rapid_{i}")
                changes.append(f"rapid_{i}_function_")
                file_operations.modify_file(test_file, change_content)
                await asyncio.sleep(0.2)  # Rapid changes

            # Wait for processing to settle
            await asyncio.sleep(10)

            # Final content should be searchable
            assertions = FileWatchingAssertions(fixture.db_path, timeout=10.0)
            final_content_found = (
                await assertions.assert_content_searchable_within_timeout(
                    "rapid_4_function_"
                )
            )

            assert final_content_found, (
                "Final content from rapid changes should be searchable"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_multiple_file_operations_concurrent(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test concurrent operations on multiple files."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create multiple files simultaneously
            files = []
            unique_markers = []

            for i in range(3):
                content = generate_unique_content(f"concurrent_{i}")
                file_path = file_operations.create_file(f"concurrent_{i}.py", content)
                files.append(file_path)
                unique_markers.append(f"concurrent_{i}_function_")
                await asyncio.sleep(0.1)  # Small delay between creations

            # Wait for all files to be processed
            await asyncio.sleep(10)

            # All files should be searchable
            assertions = FileWatchingAssertions(fixture.db_path, timeout=5.0)

            for i, marker in enumerate(unique_markers):
                found = await assertions.assert_content_searchable_within_timeout(
                    marker
                )
                assert found, f"Content from concurrent file {i} should be searchable"

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_file_watcher_respects_exclude_patterns(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test that file watcher respects exclude patterns from config."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create files that should be excluded (.log files)
            log_file = file_operations.create_file(
                "test.log", "This is a log file that should be excluded"
            )

            # Create file that should be included
            py_file = file_operations.create_file(
                "test_include.py", generate_unique_content("included")
            )

            # Wait for processing
            await asyncio.sleep(8)

            assertions = FileWatchingAssertions(fixture.db_path, timeout=5.0)

            # .log file should not be indexed
            log_indexed = await assertions.assert_content_searchable_within_timeout(
                "log file that should be excluded"
            )

            # .py file should be indexed
            py_indexed = await assertions.assert_content_searchable_within_timeout(
                "included_function_"
            )

            assert not log_indexed, "Log file should be excluded from indexing"
            assert py_indexed, "Python file should be included in indexing"

        finally:
            await fixture.stop_mcp_server()


class TestMCPServerConfigurationIntegration:
    """Test MCP server configuration with file watching."""

    @pytest.mark.asyncio
    async def test_file_watching_environment_variables(
        self, temp_project_with_monitoring
    ):
        """Test file watching configuration via environment variables."""
        fixture = temp_project_with_monitoring

        # Set additional environment variables
        env_vars = {
            "CHUNKHOUND_WATCH_ENABLED": "true",
            "CHUNKHOUND_PERIODIC_INDEX_ENABLED": "false",
            "CHUNKHOUND_DEBUG": "1",
        }

        original_env = {}
        try:
            # Set environment variables
            for key, value in env_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

            # Start server
            started = await fixture.start_mcp_server()

            if started:
                await asyncio.sleep(3)
                running = fixture.process.poll() is None
                await fixture.stop_mcp_server()

                assert running, (
                    "MCP server should run with custom file watching environment variables"
                )
            else:
                pytest.skip("Could not start MCP server with custom environment")

        finally:
            # Restore environment
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                elif key in os.environ:
                    del os.environ[key]

    @pytest.mark.asyncio
    async def test_file_watching_disabled_via_config(self):
        """Test that file watching can be disabled via configuration."""
        temp_dir = Path(tempfile.mkdtemp())
        project_dir = temp_dir / "no_watch_project"
        project_dir.mkdir(parents=True)

        try:
            # Create config with file watching disabled
            config = Config(
                database={"path": str(project_dir / "test.db"), "provider": "duckdb"},
                indexing={"watch": False},  # Disabled
            )

            async with with_mcp_server(project_dir, config) as server:
                # Server should start but without file watching
                # This is mainly testing that disabling watch doesn't break startup
                await asyncio.sleep(2)
                assert server.process.poll() is None, (
                    "Server should run even with file watching disabled"
                )

        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
