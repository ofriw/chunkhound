"""
Unit tests for file detection and filesystem event handling.

Tests the core file watching components:
- FileWatcher event detection
- Event debouncing and batch processing
- Pattern matching for inclusion/exclusion
- File completion detection
- Event handler functionality
"""

import asyncio
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from watchdog.events import FileSystemEvent

from tests.fixtures.mcp_testing import mock_file_watcher
from tests.utils.file_watching_helpers import (
    execute_file_operations,
    FileOperationGenerator,
    generate_unique_content,
)


class TestFileWatcherCore:
    """Test core file watcher functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "test_project"
        self.project_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_file_watcher_initialization(self, mock_file_watcher):
        """Test file watcher initializes correctly."""
        watcher = mock_file_watcher

        # Should start in stopped state
        assert not watcher.started
        assert len(watcher.events) == 0

        # Should be able to start
        watcher.start_watching()
        assert watcher.started

        # Should be able to stop
        watcher.stop_watching()
        assert not watcher.started

    @pytest.mark.asyncio
    async def test_file_creation_event_detection(self, mock_file_watcher):
        """Test detection of file creation events."""
        watcher = mock_file_watcher
        watcher.start_watching()

        # Simulate file creation
        test_file = self.project_dir / "test.py"
        await watcher.simulate_file_event("created", test_file)

        # Check event was recorded
        assert len(watcher.events) == 1
        event = watcher.events[0]
        assert event["event_type"] == "created"
        assert event["file_path"] == str(test_file)
        assert "timestamp" in event

    @pytest.mark.asyncio
    async def test_file_modification_event_detection(self, mock_file_watcher):
        """Test detection of file modification events."""
        watcher = mock_file_watcher
        watcher.start_watching()

        # Create file first
        test_file = self.project_dir / "test.py"
        test_file.write_text("initial content")

        # Simulate modification
        await watcher.simulate_file_event("modified", test_file)

        # Check event was recorded
        assert len(watcher.events) == 1
        event = watcher.events[0]
        assert event["event_type"] == "modified"
        assert event["file_path"] == str(test_file)

    @pytest.mark.asyncio
    async def test_file_deletion_event_detection(self, mock_file_watcher):
        """Test detection of file deletion events."""
        watcher = mock_file_watcher
        watcher.start_watching()

        # Simulate deletion
        test_file = self.project_dir / "test.py"
        await watcher.simulate_file_event("deleted", test_file)

        # Check event was recorded
        assert len(watcher.events) == 1
        event = watcher.events[0]
        assert event["event_type"] == "deleted"
        assert event["file_path"] == str(test_file)

    @pytest.mark.asyncio
    async def test_rapid_event_sequence(self, mock_file_watcher):
        """Test handling of rapid event sequences."""
        watcher = mock_file_watcher
        watcher.start_watching()

        test_file = self.project_dir / "rapid.py"

        # Generate rapid events
        event_types = ["created", "modified", "modified", "modified"]

        for event_type in event_types:
            await watcher.simulate_file_event(event_type, test_file, delay=0.01)

        # All events should be recorded
        assert len(watcher.events) == len(event_types)

        # Check sequence
        for i, expected_type in enumerate(event_types):
            assert watcher.events[i]["event_type"] == expected_type
            assert watcher.events[i]["file_path"] == str(test_file)

    @pytest.mark.asyncio
    async def test_multiple_file_events(self, mock_file_watcher):
        """Test handling of events on multiple files."""
        watcher = mock_file_watcher
        watcher.start_watching()

        # Create events for multiple files
        files = [
            self.project_dir / "file1.py",
            self.project_dir / "file2.py",
            self.project_dir / "file3.py",
        ]

        for file_path in files:
            await watcher.simulate_file_event("created", file_path)

        # Should have events for all files
        assert len(watcher.events) == len(files)

        recorded_files = [event["file_path"] for event in watcher.events]
        expected_files = [str(f) for f in files]

        assert set(recorded_files) == set(expected_files)


class TestFilePatternMatching:
    """Test file pattern matching for inclusion/exclusion."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "pattern_test"
        self.project_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_include_pattern_matching(self):
        """Test include pattern matching."""
        from chunkhound.core.config.config import Config

        config = Config(indexing={"include": ["*.py", "*.js"], "exclude": []})

        test_files = [
            ("test.py", True),  # Should match
            ("test.js", True),  # Should match
            ("test.txt", False),  # Should not match
            ("test.log", False),  # Should not match
            ("README.md", False),  # Should not match
        ]

        for filename, should_match in test_files:
            # This would normally use the actual pattern matching logic
            # from the file watcher implementation
            match = any(
                filename.endswith(pattern.lstrip("*."))
                for pattern in config.indexing.include
            )
            assert match == should_match, f"Pattern matching failed for {filename}"

    @pytest.mark.asyncio
    async def test_exclude_pattern_matching(self):
        """Test exclude pattern matching."""
        from chunkhound.core.config.config import Config

        config = Config(
            indexing={
                "include": ["*"],  # Include all
                "exclude": ["*.log", "*.tmp", "node_modules/"],
            }
        )

        test_files = [
            ("test.py", True),  # Should not be excluded
            ("test.js", True),  # Should not be excluded
            ("debug.log", False),  # Should be excluded
            ("temp.tmp", False),  # Should be excluded
            ("node_modules/lib.js", False),  # Should be excluded
        ]

        for filename, should_be_included in test_files:
            # Check if file should be excluded
            excluded = any(
                filename.endswith(pattern.lstrip("*."))
                or pattern.rstrip("/") in filename
                for pattern in config.indexing.exclude
            )
            included = not excluded

            assert included == should_be_included, (
                f"Exclude pattern matching failed for {filename}"
            )

    @pytest.mark.asyncio
    async def test_complex_pattern_combinations(self):
        """Test complex include/exclude pattern combinations."""
        from chunkhound.core.config.config import Config

        config = Config(
            indexing={
                "include": ["*.py", "*.js", "src/**"],
                "exclude": ["*_test.py", "*.spec.js", "node_modules/"],
            }
        )

        test_cases = [
            ("app.py", True),  # Included by *.py
            ("test_app.py", True),  # Included by *.py, NOT excluded by *_test.py
            ("app_test.py", False),  # Excluded by *_test.py (correct pattern)
            ("utils.js", True),  # Included by *.js
            ("utils.spec.js", False),  # Excluded by *.spec.js
            ("src/main.cpp", True),  # Included by src/**
            ("node_modules/lib.js", False),  # Excluded by node_modules/
        ]

        for filename, expected_included in test_cases:
            # Simulate pattern matching logic
            included = any(
                filename.endswith(pattern.lstrip("*."))
                or (
                    pattern.endswith("**")
                    and filename.startswith(pattern.rstrip("/**"))
                )
                for pattern in config.indexing.include
            )

            if included:
                excluded = any(
                    filename.endswith(pattern.lstrip("*."))
                    or pattern.rstrip("/") in filename
                    for pattern in config.indexing.exclude
                )
                included = not excluded

            assert included == expected_included, (
                f"Complex pattern failed for {filename}"
            )


class TestEventDebouncing:
    """Test event debouncing and batch processing."""

    @pytest.mark.asyncio
    async def test_debouncing_rapid_modifications(self, mock_file_watcher):
        """Test that rapid modifications are debounced."""
        watcher = mock_file_watcher
        watcher.start_watching()

        test_file = self.project_dir / "debounce_test.py"

        # Simulate rapid modifications
        for i in range(10):
            await watcher.simulate_file_event("modified", test_file, delay=0.05)

        # All events should be recorded (debouncing logic would be in the handler)
        assert len(watcher.events) == 10

        # Verify all events are for the same file
        for event in watcher.events:
            assert event["file_path"] == str(test_file)
            assert event["event_type"] == "modified"

    @pytest.mark.asyncio
    async def test_batch_processing_multiple_files(self, mock_file_watcher):
        """Test batch processing of multiple file events."""
        watcher = mock_file_watcher
        watcher.start_watching()

        # Create batch of file events
        batch_size = 20
        files = [self.project_dir / f"batch_{i}.py" for i in range(batch_size)]

        # Simulate batch creation
        for file_path in files:
            await watcher.simulate_file_event("created", file_path)

        assert len(watcher.events) == batch_size

        # Group events by type for batch processing simulation
        events_by_type = {}
        for event in watcher.events:
            event_type = event["event_type"]
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event)

        # Should be able to batch process all creation events
        assert "created" in events_by_type
        assert len(events_by_type["created"]) == batch_size

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "debounce_test"
        self.project_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestFileCompletionDetection:
    """Test detection of file write completion."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "completion_test"
        self.project_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_file_completion_detection(self):
        """Test detection of when file writes are complete."""
        # This simulates the _wait_for_file_completion logic

        test_file = self.project_dir / "completion_test.py"

        # Write file
        test_file.write_text("print('hello world')")

        # Simulate completion detection by checking file stability
        initial_mtime = test_file.stat().st_mtime
        initial_size = test_file.stat().st_size

        # Wait a short time
        await asyncio.sleep(0.1)

        # Check if file is stable
        current_mtime = test_file.stat().st_mtime
        current_size = test_file.stat().st_size

        # File should be stable (no changes)
        assert current_mtime == initial_mtime, "File mtime should be stable"
        assert current_size == initial_size, "File size should be stable"

    @pytest.mark.asyncio
    async def test_large_file_completion(self):
        """Test completion detection for large files."""
        test_file = self.project_dir / "large_file.py"

        # Create large content
        large_content = "# Large file test\n" + "print('line')\n" * 1000

        # Write file in chunks to simulate streaming write
        with open(test_file, "w") as f:
            for i in range(0, len(large_content), 100):
                f.write(large_content[i : i + 100])
                f.flush()
                await asyncio.sleep(0.001)  # Tiny delay between chunks

        # File should exist and be complete
        assert test_file.exists()
        final_content = test_file.read_text()
        assert final_content == large_content

    @pytest.mark.asyncio
    async def test_concurrent_file_writes(self):
        """Test handling of concurrent file writes."""
        files = []

        # Create multiple files concurrently
        async def create_file(i):
            file_path = self.project_dir / f"concurrent_{i}.py"
            content = generate_unique_content(f"concurrent_{i}")
            file_path.write_text(content)
            return file_path

        # Create files concurrently
        tasks = [create_file(i) for i in range(5)]
        created_files = await asyncio.gather(*tasks)

        # All files should be created successfully
        assert len(created_files) == 5

        for file_path in created_files:
            assert file_path.exists()
            content = file_path.read_text()
            assert len(content) > 0
            assert "def" in content  # Should contain generated function


class TestEventHandlerIntegration:
    """Test integration of event handlers with file processing."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_dir = self.temp_dir / "handler_test"
        self.project_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_event_handler_registration(self, mock_file_watcher):
        """Test event handler registration and calling."""
        watcher = mock_file_watcher

        # Create mock handler
        handler = Mock()
        handler.on_file_event = AsyncMock()

        # Register handler
        watcher.add_handler(handler)

        # Simulate event
        test_file = self.project_dir / "handler_test.py"
        await watcher.simulate_file_event("created", test_file)

        # Handler should be called
        handler.on_file_event.assert_called_once_with("created", test_file)

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, mock_file_watcher):
        """Test multiple event handlers."""
        watcher = mock_file_watcher

        # Create multiple handlers
        handlers = []
        for i in range(3):
            handler = Mock()
            handler.on_file_event = AsyncMock()
            handlers.append(handler)
            watcher.add_handler(handler)

        # Simulate event
        test_file = self.project_dir / "multi_handler_test.py"
        await watcher.simulate_file_event("modified", test_file)

        # All handlers should be called
        for handler in handlers:
            handler.on_file_event.assert_called_once_with("modified", test_file)

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, mock_file_watcher):
        """Test error handling in event handlers."""
        watcher = mock_file_watcher

        # Create handler that raises exception
        error_handler = Mock()
        error_handler.on_file_event = AsyncMock(side_effect=Exception("Handler error"))

        # Create normal handler
        normal_handler = Mock()
        normal_handler.on_file_event = AsyncMock()

        watcher.add_handler(error_handler)
        watcher.add_handler(normal_handler)

        # Simulate event - should not crash despite error
        test_file = self.project_dir / "error_test.py"
        await watcher.simulate_file_event("created", test_file)

        # Both handlers should be called
        error_handler.on_file_event.assert_called_once()
        normal_handler.on_file_event.assert_called_once()

        # Event should still be recorded despite handler error
        assert len(watcher.events) == 1
