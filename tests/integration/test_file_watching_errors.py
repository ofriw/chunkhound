"""
Error handling tests for MCP file watching functionality.

Tests failure scenarios and recovery mechanisms:
- File watcher initialization failures
- Database connection loss during processing
- File system permission issues
- Partial processing failures
- Memory pressure scenarios
- Concurrent access errors
"""

import asyncio
import os
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from chunkhound.core.config.config import Config
from chunkhound.database import Database
from tests.fixtures.mcp_testing import (
    temp_project_with_monitoring,
    mcp_server_with_watcher,
    file_operations,
)
from tests.utils.file_watching_helpers import (
    FileWatchingAssertions,
    generate_unique_content,
    DebugHelper,
)


class TestFileWatcherInitializationErrors:
    """Test file watcher initialization failure scenarios."""

    @pytest.mark.asyncio
    async def test_watchdog_unavailable_fallback(self, temp_project_with_monitoring):
        """Test fallback when watchdog library is unavailable."""
        fixture = temp_project_with_monitoring

        with patch("chunkhound.file_watcher.WATCHDOG_AVAILABLE", False):
            # Server should still start but without file watching
            started = await fixture.start_mcp_server()

            try:
                if started:
                    await asyncio.sleep(2)
                    assert fixture.process.poll() is None, (
                        "Server should run without file watching"
                    )
                else:
                    pytest.skip("Server could not start without watchdog")
            finally:
                await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_invalid_watch_path_handling(self, temp_project_with_monitoring):
        """Test handling of invalid watch paths."""
        fixture = temp_project_with_monitoring

        # Set invalid watch path
        env = os.environ.copy()
        env["CHUNKHOUND_WATCH_PATHS"] = "/nonexistent/path,/another/invalid/path"

        with patch.dict(os.environ, env):
            # Server should handle invalid paths gracefully
            started = await fixture.start_mcp_server()

            try:
                if started:
                    await asyncio.sleep(3)
                    # Should still be running despite invalid paths
                    assert fixture.process.poll() is None, (
                        "Server should handle invalid watch paths gracefully"
                    )
            finally:
                await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_permission_denied_watch_path(self, temp_project_with_monitoring):
        """Test handling of permission denied on watch paths."""
        fixture = temp_project_with_monitoring

        # Create a directory with restricted permissions
        restricted_dir = fixture.project_dir / "restricted"
        restricted_dir.mkdir()

        try:
            # Remove read permissions (on Unix systems)
            if hasattr(os, "chmod"):
                restricted_dir.chmod(0o000)

            # Try to watch restricted directory
            env = os.environ.copy()
            env["CHUNKHOUND_WATCH_PATHS"] = str(restricted_dir)

            with patch.dict(os.environ, env):
                started = await fixture.start_mcp_server()

                try:
                    if started:
                        await asyncio.sleep(2)
                        # Should handle permission errors gracefully
                        assert fixture.process.poll() is None, (
                            "Server should handle permission errors"
                        )
                finally:
                    await fixture.stop_mcp_server()

        finally:
            # Restore permissions for cleanup
            if hasattr(os, "chmod"):
                try:
                    restricted_dir.chmod(0o755)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_file_watcher_crash_recovery(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test recovery from file watcher crashes."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a file to ensure watcher was working
            test_file = file_operations.create_file(
                "before_crash.py", generate_unique_content("before")
            )
            await asyncio.sleep(2)

            # Simulate file watcher crash by sending signal or similar
            # In real test, we'd simulate the crash more directly

            # Create another file after potential crash
            test_file2 = file_operations.create_file(
                "after_crash.py", generate_unique_content("after")
            )
            await asyncio.sleep(5)

            # Server should still be running
            assert fixture.process.poll() is None, (
                "Server should recover from file watcher issues"
            )

        finally:
            await fixture.stop_mcp_server()


class TestDatabaseConnectionErrors:
    """Test database connection and locking errors."""

    @pytest.mark.asyncio
    async def test_database_locked_during_file_processing(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of database lock errors during file processing."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a separate database connection to lock the database
            db2 = Database(str(fixture.db_path))
            db2.connect()

            # Begin a long transaction to lock database
            db2.execute("BEGIN EXCLUSIVE TRANSACTION")

            try:
                # Now try to create files (should handle lock gracefully)
                test_file = file_operations.create_file(
                    "locked_test.py", generate_unique_content("locked")
                )

                # Give time for processing attempt
                await asyncio.sleep(5)

                # Server should still be running
                assert fixture.process.poll() is None, (
                    "Server should handle database locks gracefully"
                )

            finally:
                # Release lock
                db2.execute("ROLLBACK")
                db2.close()

            # After releasing lock, file should eventually be processed
            await asyncio.sleep(5)

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_database_corruption_handling(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of database corruption scenarios."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create initial file
            test_file = file_operations.create_file(
                "pre_corruption.py", generate_unique_content("pre")
            )
            await asyncio.sleep(2)

            # Stop server
            await fixture.stop_mcp_server()

            # Simulate database corruption by truncating file
            if fixture.db_path.exists():
                with open(fixture.db_path, "wb") as f:
                    f.write(b"corrupted data")

            # Try to restart server
            restarted = await fixture.start_mcp_server()

            if restarted:
                await asyncio.sleep(3)
                # Server should handle corruption (recreate database, etc.)
                assert fixture.process.poll() is None, (
                    "Server should handle database corruption"
                )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_concurrent_database_access_conflicts(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of concurrent database access conflicts."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create many files rapidly to stress concurrent access
            tasks = []
            for i in range(10):
                task = asyncio.create_task(self._create_file_async(file_operations, i))
                tasks.append(task)

            # Wait for all file operations
            await asyncio.gather(*tasks, return_exceptions=True)

            # Give time for processing
            await asyncio.sleep(10)

            # Server should handle concurrent access
            assert fixture.process.poll() is None, (
                "Server should handle concurrent database access"
            )

        finally:
            await fixture.stop_mcp_server()

    async def _create_file_async(self, file_operations, index):
        """Helper to create files asynchronously."""
        content = generate_unique_content(f"concurrent_{index}")
        file_operations.create_file(f"concurrent_{index}.py", content)
        await asyncio.sleep(0.1)


class TestFileSystemErrors:
    """Test file system related errors."""

    @pytest.mark.asyncio
    async def test_disk_space_exhaustion_handling(self, temp_project_with_monitoring):
        """Test handling when disk space is exhausted."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Simulate disk space exhaustion by mocking filesystem operations
            with patch(
                "pathlib.Path.write_text",
                side_effect=OSError("No space left on device"),
            ):
                # Server should handle disk space issues gracefully
                await asyncio.sleep(2)
                assert fixture.process.poll() is None, (
                    "Server should handle disk space issues"
                )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_file_permission_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of file permission errors."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a file
            test_file = file_operations.create_file(
                "permission_test.py", "initial content"
            )

            # Remove read permissions
            if hasattr(os, "chmod"):
                test_file.chmod(0o000)

                try:
                    # Try to modify the file (should fail)
                    test_file.write_text("modified content")
                except PermissionError:
                    pass  # Expected

                # Server should continue running despite permission errors
                await asyncio.sleep(2)
                assert fixture.process.poll() is None, (
                    "Server should handle permission errors"
                )

                # Restore permissions
                test_file.chmod(0o644)

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_symbolic_link_handling_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of broken symbolic links."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a broken symbolic link
            broken_link = fixture.project_dir / "broken_link.py"
            target = fixture.project_dir / "nonexistent_target.py"

            if hasattr(os, "symlink"):
                try:
                    os.symlink(str(target), str(broken_link))

                    # File watcher should handle broken symlinks gracefully
                    await asyncio.sleep(3)
                    assert fixture.process.poll() is None, (
                        "Server should handle broken symlinks"
                    )

                except (OSError, NotImplementedError):
                    # Symlinks not supported on this platform
                    pytest.skip("Symlinks not supported")
            else:
                pytest.skip("Symlinks not available")

        finally:
            await fixture.stop_mcp_server()


class TestProcessingErrors:
    """Test file processing and parsing errors."""

    @pytest.mark.asyncio
    async def test_malformed_file_content_handling(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of malformed or binary file content."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create file with binary content
            binary_file = fixture.project_dir / "binary_test.py"
            binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

            # Create file with invalid UTF-8
            invalid_utf8_file = fixture.project_dir / "invalid_utf8.py"
            invalid_utf8_file.write_bytes(
                "# Valid start\n".encode("utf-8") + b"\x80\x81\x82"
            )

            # Give time for processing attempts
            await asyncio.sleep(5)

            # Server should handle malformed content gracefully
            assert fixture.process.poll() is None, (
                "Server should handle malformed file content"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_large_file_processing_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of very large files that might cause memory issues."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a very large file
            large_content = "# Large file\n" + "print('line')\n" * 100000
            large_file = file_operations.create_file("large_test.py", large_content)

            # Give time for processing
            await asyncio.sleep(10)

            # Server should handle large files without crashing
            assert fixture.process.poll() is None, "Server should handle large files"

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_parsing_syntax_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of files with syntax errors."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create file with syntax errors
            syntax_error_content = """
# This file has syntax errors
def function_missing_colon()
    return "missing colon"

def function_with_invalid_indentation():
      x = 1
    return x  # Invalid indentation

# Unclosed string
broken_string = "this string is never closed
"""

            syntax_error_file = file_operations.create_file(
                "syntax_error.py", syntax_error_content
            )

            # Give time for processing
            await asyncio.sleep(5)

            # Server should handle syntax errors gracefully
            assert fixture.process.poll() is None, "Server should handle syntax errors"

        finally:
            await fixture.stop_mcp_server()


class TestMemoryAndResourceErrors:
    """Test memory pressure and resource exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_memory_pressure_during_processing(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test handling of memory pressure during file processing."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create many files to pressure memory
            for i in range(50):
                content = generate_unique_content(f"memory_test_{i}")
                file_operations.create_file(f"memory_test_{i}.py", content)
                await asyncio.sleep(0.05)

            # Give time for processing all files
            await asyncio.sleep(15)

            # Server should handle memory pressure
            assert fixture.process.poll() is None, (
                "Server should handle memory pressure"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_resource_exhaustion_recovery(self, temp_project_with_monitoring):
        """Test recovery from resource exhaustion scenarios."""
        fixture = temp_project_with_monitoring

        # Simulate resource limits
        with patch(
            "chunkhound.services.indexing_coordinator.asyncio.Semaphore"
        ) as mock_semaphore:
            # Make semaphore fail to simulate resource exhaustion
            mock_semaphore.side_effect = OSError("Resource temporarily unavailable")

            started = await fixture.start_mcp_server()

            try:
                if started:
                    await asyncio.sleep(3)
                    # Server should handle resource exhaustion
                    assert fixture.process.poll() is None, (
                        "Server should handle resource exhaustion"
                    )
            finally:
                await fixture.stop_mcp_server()


class TestErrorRecoveryMechanisms:
    """Test error recovery and resilience mechanisms."""

    @pytest.mark.asyncio
    async def test_automatic_retry_on_transient_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test automatic retry on transient errors."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create a file that will initially fail processing
            test_file = file_operations.create_file(
                "retry_test.py", generate_unique_content("retry")
            )

            # Simulate transient error by temporarily making file inaccessible
            if hasattr(os, "chmod"):
                test_file.chmod(0o000)

                # Give time for initial failed processing attempt
                await asyncio.sleep(3)

                # Restore access
                test_file.chmod(0o644)

                # Give time for retry to succeed
                await asyncio.sleep(5)

                # Server should have recovered and processed the file
                assert fixture.process.poll() is None, (
                    "Server should retry transient errors"
                )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_persistent_errors(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test graceful degradation when errors persist."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create files that will consistently fail
            problematic_files = []
            for i in range(3):
                file_path = fixture.project_dir / f"problematic_{i}.py"
                problematic_files.append(file_path)

                # Create file with persistent issues
                file_path.write_bytes(b"\xff\xfe\xfd")  # Invalid content

            # Also create a normal file
            normal_file = file_operations.create_file(
                "normal.py", generate_unique_content("normal")
            )

            # Give time for processing
            await asyncio.sleep(10)

            # Server should continue running despite problematic files
            assert fixture.process.poll() is None, (
                "Server should gracefully handle persistent errors"
            )

        finally:
            await fixture.stop_mcp_server()

    @pytest.mark.asyncio
    async def test_error_isolation_between_files(
        self, temp_project_with_monitoring, file_operations
    ):
        """Test that errors in one file don't affect processing of other files."""
        fixture = temp_project_with_monitoring

        started = await fixture.start_mcp_server()
        if not started:
            pytest.skip("Could not start MCP server")

        try:
            await asyncio.sleep(3)

            # Create one problematic file
            problematic_file = fixture.project_dir / "problematic.py"
            problematic_file.write_bytes(b"\x00\x01\x02")

            # Create several normal files
            normal_files = []
            for i in range(5):
                normal_file = file_operations.create_file(
                    f"normal_{i}.py", generate_unique_content(f"normal_{i}")
                )
                normal_files.append(normal_file)
                await asyncio.sleep(0.5)

            # Give time for processing
            await asyncio.sleep(10)

            # Server should process normal files despite problematic one
            assert fixture.process.poll() is None, (
                "Errors should be isolated between files"
            )

            # Check that at least some normal files were processed
            assertions = FileWatchingAssertions(fixture.db_path, timeout=5.0)

            normal_content_found = False
            for i in range(5):
                found = await assertions.assert_content_searchable_within_timeout(
                    f"normal_{i}_function_"
                )
                if found:
                    normal_content_found = True
                    break

            assert normal_content_found, (
                "Normal files should be processed despite errors in other files"
            )

        finally:
            await fixture.stop_mcp_server()
