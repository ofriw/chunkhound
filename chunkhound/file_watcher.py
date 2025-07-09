#!/usr/bin/env python3
"""
Filesystem Event Watcher for ChunkHound MCP Server

Queue-based filesystem event monitoring with offline catch-up support.
Designed to prevent DuckDB WAL corruption by serializing all database operations
through the main MCP server thread.
"""

import asyncio
import collections
import json
import logging
import os
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

# Set up logger
logger = logging.getLogger(__name__)


# Debug logging function for MCP-safe debugging
def debug_log(event_type, **data):
    """Log debug events to file (MCP-safe)."""
    try:
        if os.environ.get("CHUNKHOUND_DEBUG_MODE") == "1":
            debug_dir = Path(".mem/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"chunkhound-watcher-debug-{os.getpid()}.jsonl"

            entry = {
                "timestamp": time.time(),
                "timestamp_iso": datetime.now().isoformat(),
                "event": event_type,
                "process_id": os.getpid(),
                "data": data,
            }

            with open(debug_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
                f.flush()
    except:
        pass  # Silent fail for MCP safety


# Import Language enum for centralized extension management
from chunkhound.core.types.common import Language

# Use centralized extension list from Language enum
SUPPORTED_EXTENSIONS = Language.get_all_extensions()
# Add special case filenames that are checked separately
SUPPORTED_FILENAMES = {"Makefile", "makefile", "GNUmakefile", "gnumakefile"}


# Protocol for event handlers
class EventHandlerProtocol(Protocol):
    def on_modified(self, event: Any) -> None: ...
    def on_created(self, event: Any) -> None: ...
    def on_moved(self, event: Any) -> None: ...
    def on_deleted(self, event: Any) -> None: ...


# Handle conditional imports for watchdog
try:
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None

    # Create a dummy base class when watchdog is not available
    class FileSystemEventHandler:
        def __init__(self):
            pass

        def on_modified(self, event):
            pass

        def on_created(self, event):
            pass

        def on_moved(self, event):
            pass

        def on_deleted(self, event):
            pass


# Disable logging for this module to prevent MCP interference
logging.getLogger(__name__).setLevel(logging.CRITICAL + 1)


@dataclass
class FileChangeEvent:
    """Represents a file change event to be processed."""

    path: Path
    event_type: str  # 'created', 'modified', 'moved', 'deleted'
    timestamp: float
    old_path: Path | None = None  # For move events


class ChunkHoundEventHandler(FileSystemEventHandler):
    """Filesystem event handler that buffers events for polling."""

    def __init__(self, include_patterns: set[str] | None = None):
        super().__init__()
        debug_log(
            "handler_init",
            include_patterns=list(include_patterns) if include_patterns else None,
        )
        # Thread-safe event buffer - simple deque with lock
        self._events = collections.deque(maxlen=1000)
        self._lock = threading.Lock()
        self.include_patterns = include_patterns or SUPPORTED_EXTENSIONS

    def get_events(self) -> list[FileChangeEvent]:
        """Get and clear all buffered events. Thread-safe for polling."""
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on extension and patterns."""
        # For deleted files, we can't check is_file() since they no longer exist
        # Check if it's a supported file using centralized logic
        return Language.is_supported_file(file_path)

    def _buffer_event(self, path: Path, event_type: str, old_path: Path | None = None):
        """Buffer a file change event if it passes filters."""
        debug_log("buffer_event_called", path=str(path), watchdog_event_type=event_type)

        # Enhanced diagnostic logging for debugging
        import os
        import sys

        # ALWAYS log file events to stderr in debug mode to trace missing events
        if os.environ.get("CHUNKHOUND_DEBUG"):
            # print("=== BUFFER EVENT ATTEMPT ===", file=sys.stderr)
            # print(f"Path: {path}", file=sys.stderr)
            # print(f"Event Type: {event_type}", file=sys.stderr)
            # print(f"File Exists: {path.exists()}", file=sys.stderr)
            # print(f"File Extension: {path.suffix}", file=sys.stderr)

            pass
        # For deletion events, always check extension pattern
        # For other events, also verify file exists
        if event_type != "deleted" and not path.is_file():
            if os.environ.get("CHUNKHOUND_DEBUG"):
                # print("❌ FILE DOES NOT EXIST", file=sys.stderr)
                # print("==========================", file=sys.stderr)
                pass
            return

        should_process = self._should_process_file(path)
        debug_log(
            "should_process_check",
            path=str(path),
            should_process=should_process,
            file_suffix=path.suffix,
        )

        if os.environ.get("CHUNKHOUND_DEBUG"):
            # print(f"Should Process File: {should_process}", file=sys.stderr)
            pass
        if not should_process:
            debug_log(
                "buffer_event_rejected", path=str(path), reason="should_not_process"
            )
            if os.environ.get("CHUNKHOUND_DEBUG"):
                # print("❌ FILE SHOULD NOT BE PROCESSED", file=sys.stderr)
                # print("==========================", file=sys.stderr)
                pass
            return

        event_timestamp = time.time()

        event = FileChangeEvent(
            path=path,
            event_type=event_type,
            timestamp=event_timestamp,
            old_path=old_path,
        )

        # Add event to thread-safe buffer
        with self._lock:
            self._events.append(event)
            buffer_size = len(self._events)

        logger.debug(
            f"TIMING: Event buffered at {event_timestamp:.6f} - {event_type} {path}"
        )
        debug_log(
            "event_buffered_success",
            path=str(path),
            watchdog_event_type=event_type,
            buffer_size=buffer_size,
        )

        if os.environ.get("CHUNKHOUND_DEBUG"):
            # print("✅ EVENT SUCCESSFULLY BUFFERED", file=sys.stderr)
            # print(f"Buffer Size After: {buffer_size}", file=sys.stderr)
            # print("==========================", file=sys.stderr)

            pass
    def on_any_event(self, event):
        """Log all events for debugging - this should be called for EVERY event."""
        debug_log(
            "on_any_event_called",
            watchdog_event_type=event.event_type,
            path=str(event.src_path),
            is_directory=event.is_directory,
            has_dest_path=hasattr(event, "dest_path"),
        )

    def on_modified(self, event):
        """Handle file modification events."""
        import os
        import sys

        # ALWAYS log watchdog events to stderr when debug is enabled
        if os.environ.get("CHUNKHOUND_DEBUG"):
            # print(
            #     f"🔍 WATCHDOG on_modified: {event.src_path} (is_dir: {event.is_directory})",
            #     file=sys.stderr,
            # )
            pass

        debug_log(
            "on_modified_called",
            path=str(event.src_path),
            is_directory=event.is_directory,
            watchdog_event_type=getattr(event, "event_type", "unknown"),
        )

        if not event.is_directory:
            path_str = str(event.src_path)
            logger.debug(
                f"TIMING: File modified detected at {time.time():.6f} - {event.src_path}"
            )
            debug_log(
                "on_modified_calling_queue",
                path=path_str,
                watchdog_event_type="modified",
            )
            self._buffer_event(Path(event.src_path), "modified")

    def on_created(self, event):
        """Handle file creation events."""
        import os
        import sys

        # ALWAYS log watchdog events to stderr when debug is enabled
        if os.environ.get("CHUNKHOUND_DEBUG"):
            # print(
            #     f"🔍 WATCHDOG on_created: {event.src_path} (is_dir: {event.is_directory})",
            #     file=sys.stderr,
            # )
            pass

        debug_log(
            "on_created_called",
            path=str(event.src_path),
            is_directory=event.is_directory,
            watchdog_event_type=getattr(event, "event_type", "unknown"),
        )

        if not event.is_directory:
            path_str = str(event.src_path)
            debug_log(
                "on_created_processing",
                path=path_str,
                file_exists=Path(path_str).exists(),
            )

            # Diagnostic logging for file creation debugging
            if os.environ.get("CHUNKHOUND_DEBUG"):
                # print("=== FILE CREATION EVENT DETECTED ===", file=sys.stderr)
                # print(f"File: {event.src_path}", file=sys.stderr)
                # print(f"Timestamp: {time.time():.6f}", file=sys.stderr)
                # print(f"Is Directory: {event.is_directory}", file=sys.stderr)
                # print("====================================", file=sys.stderr)
                pass
            debug_log(
                "on_created_calling_queue", path=path_str, watchdog_event_type="created"
            )
            self._buffer_event(Path(event.src_path), "created")

    def on_moved(self, event):
        """Handle file move/rename events."""
        if not event.is_directory:
            old_path = Path(event.src_path)
            new_path = Path(event.dest_path)

            # Buffer deletion of old path
            if self._should_process_file(old_path):
                self._buffer_event(old_path, "deleted")

            # Buffer creation of new path
            self._buffer_event(new_path, "moved", old_path)

    def on_deleted(self, event):
        """Handle file deletion events."""
        debug_log(
            "on_deleted_called",
            path=str(event.src_path),
            is_directory=event.is_directory,
        )

        if not event.is_directory:
            logger.debug(
                f"TIMING: File deleted detected at {time.time():.6f} - {event.src_path}"
            )
            debug_log(
                "on_deleted_calling_queue",
                path=str(event.src_path),
                watchdog_event_type="deleted",
            )
            self._buffer_event(Path(event.src_path), "deleted")


class FileWatcher:
    """
    Simple filesystem watcher with polling-based event consumption.

    Uses thread-safe buffer for events, no asyncio dependencies.
    Completely decoupled from database operations.
    """

    def __init__(
        self, watch_paths: list[Path], include_patterns: set[str] | None = None
    ):
        """
        Initialize the file watcher.

        Args:
            watch_paths: List of paths to watch for changes
            include_patterns: File extensions to monitor (default: from Language enum)
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog package is required for filesystem watching")

        self.watch_paths = watch_paths
        self.include_patterns = include_patterns or SUPPORTED_EXTENSIONS

        self.observer: Any | None = None
        self.event_handler = ChunkHoundEventHandler(include_patterns)
        self.is_watching = False

    def get_events(self) -> list[FileChangeEvent]:
        """Get all buffered events for polling. Thread-safe."""
        return self.event_handler.get_events()

    def start(self) -> bool:
        """Start filesystem watching. Returns True if successful."""
        if not WATCHDOG_AVAILABLE:
            # Improved error reporting for missing watchdog
            import sys

            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(
                    # "⚠️  WATCHDOG UNAVAILABLE: File modification detection disabled",
                    # file=sys.stderr,
                # )
                pass
                # print(
                    # "   This means file changes will NOT be detected in real-time",
                    # file=sys.stderr,
                # )
                pass
                # print("   Install watchdog: pip install watchdog", file=sys.stderr)
            return False

        if self.is_watching:
            return True

        try:
            if WATCHDOG_AVAILABLE and Observer is not None:
                self.observer = Observer()

                # Set up watches for each path
                for watch_path in self.watch_paths:
                    if watch_path.exists() and watch_path.is_dir():
                        if self.observer is not None:
                            debug_log(
                                "scheduling_watch",
                                path=str(watch_path),
                                recursive=True,
                                handler_methods=[
                                    m
                                    for m in dir(self.event_handler)
                                    if m.startswith("on_")
                                ],
                            )

                            if "CHUNKHOUND_DEBUG" in os.environ:
                                import sys

                                # print(
                                    # f"🔍 WATCHDOG: Scheduling watch for {watch_path}",
                                    # file=sys.stderr,
                                # )
                                pass

                            self.observer.schedule(
                                self.event_handler, str(watch_path), recursive=True
                            )
                            debug_log("watch_scheduled", path=str(watch_path))
                        else:
                            if "CHUNKHOUND_DEBUG" in os.environ:
                                import sys

                                # print(
                                    # f"❌ WATCHDOG: Observer is None, cannot schedule {watch_path}",
                                    # file=sys.stderr,
                                # )
                                pass
                    else:
                        if "CHUNKHOUND_DEBUG" in os.environ:
                            import sys

                            # print(
                                # f"❌ WATCHDOG: Path does not exist or is not directory: {watch_path}",
                                # file=sys.stderr,
                            # )
                            pass

                if self.observer is not None:
                    debug_log(
                        "observer_starting",
                        watch_paths=[str(p) for p in self.watch_paths],
                        handler_type=type(self.event_handler).__name__,
                    )

                    if "CHUNKHOUND_DEBUG" in os.environ:
                        import sys

                        # print(
                            # f"🔍 WATCHDOG: Starting observer for {len(self.watch_paths)} paths",
                            # file=sys.stderr,
                        # )
                        pass

                    self.observer.start()
                    self.is_watching = True

                    if "CHUNKHOUND_DEBUG" in os.environ:
                        import sys

                        # print(
                            # f"✅ WATCHDOG: Observer started successfully (alive: {self.observer.is_alive()})",
                            # file=sys.stderr,
                        # )
                        pass

                    debug_log("observer_started", is_alive=self.observer.is_alive())
                    return True
                else:
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        import sys

                        # print(
                            # "❌ WATCHDOG: Observer is None after creation",
                            # file=sys.stderr,
                        # )
                        pass

            return False

        except Exception as e:
            # Log the error to help debug watchdog issues
            if "CHUNKHOUND_DEBUG" in os.environ:
                import sys

                # print(
                    # f"❌ WATCHDOG: Failed to start file watching: {e}", file=sys.stderr
                # )
                pass
                import traceback

                # traceback.print_exc(file=sys.stderr)
            # Still fail gracefully - MCP server continues without filesystem watching
            return False

    def stop(self):
        """Stop filesystem watching and cleanup resources."""
        self.is_watching = False

        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            except Exception:
                pass

        self.observer = None

    def is_available(self) -> bool:
        """Check if filesystem watching is available and working."""
        return WATCHDOG_AVAILABLE and self.is_watching


async def scan_for_offline_changes(
    watch_paths: list[Path],
    last_scan_time: float,
    include_patterns: set[str] | None = None,
    timeout: float = 5.0,
) -> list[FileChangeEvent]:
    """
    Scan for files that changed while the server was offline.

    Args:
        watch_paths: Paths to scan for changes
        last_scan_time: Timestamp of last scan (files modified after this will be included)
        include_patterns: File extensions to include
        timeout: Maximum time to spend scanning (prevents MCP startup delays)

    Returns:
        List of FileChangeEvent objects for modified files
    """
    if include_patterns is None:
        include_patterns = SUPPORTED_EXTENSIONS

    offline_changes = []
    processed_count = 0
    scan_start_time = time.time()

    def should_process_file(file_path: Path) -> bool:
        """Check if file should be processed."""
        if not file_path.is_file():
            return False
        suffix = file_path.suffix.lower()
        return suffix in include_patterns

    for watch_path in watch_paths:
        if not watch_path.exists() or not watch_path.is_dir():
            continue

        try:
            # Walk through all files in the directory
            for file_path in watch_path.rglob("*"):
                # Check timeout to prevent excessive MCP startup delays
                if time.time() - scan_start_time > timeout:
                    break

                if not should_process_file(file_path):
                    continue

                try:
                    # Check if file was modified after last scan
                    mtime = file_path.stat().st_mtime
                    if mtime > last_scan_time:
                        offline_changes.append(
                            FileChangeEvent(
                                path=file_path, event_type="modified", timestamp=mtime
                            )
                        )

                    # Yield control to event loop every 50 files to prevent blocking
                    processed_count += 1
                    if processed_count % 50 == 0:
                        await asyncio.sleep(0)

                except OSError:
                    # Skip files that can't be accessed
                    continue

        except Exception:
            # Skip directories that can't be accessed
            continue

    return offline_changes


def get_watch_paths_from_env() -> list[Path]:
    """
    Get watch paths from environment configuration.

    Returns:
        List of paths to watch, defaults to project root directory
    """
    # Import project detection
    try:
        from .utils.project_detection import get_project_watch_paths

        return get_project_watch_paths()
    except ImportError:
        pass

    paths_env = os.environ.get("CHUNKHOUND_WATCH_PATHS", "")

    if paths_env:
        if "CHUNKHOUND_DEBUG" in os.environ:
            import sys

            # print(
                # f"🔍 WATCHDOG: Using CHUNKHOUND_WATCH_PATHS environment variable: {paths_env}",
                # file=sys.stderr,
            # )
            pass

        logging.info(
            f"FileWatcher: Using CHUNKHOUND_WATCH_PATHS environment variable: {paths_env}"
        )
        # Parse comma-separated paths
        path_strings = [p.strip() for p in paths_env.split(",") if p.strip()]
        paths = []

        for path_str in path_strings:
            try:
                path = Path(path_str).resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        import sys

                        # print(f"✅ WATCHDOG: Added watch path: {path}", file=sys.stderr)
                    logging.info(f"FileWatcher: Added watch path: {path}")
                else:
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        import sys

                        # print(
                            # f"❌ WATCHDOG: Skipping invalid watch path: {path_str}",
                            # file=sys.stderr,
                        # )
                        pass
                    logging.warning(
                        f"FileWatcher: Skipping invalid watch path: {path_str}"
                    )
            except Exception as e:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    import sys

                    # print(
                        # f"❌ WATCHDOG: Failed to resolve watch path '{path_str}': {e}",
                        # file=sys.stderr,
                    # )
                    pass
                logging.warning(
                    f"FileWatcher: Failed to resolve watch path '{path_str}': {e}"
                )
                continue

        if paths:
            return paths
        else:
            if "CHUNKHOUND_DEBUG" in os.environ:
                import sys

                # print(
                    # "❌ WATCHDOG: No valid paths from CHUNKHOUND_WATCH_PATHS, falling back to current directory",
                    # file=sys.stderr,
                # )
                pass
            logging.warning(
                "FileWatcher: No valid paths from CHUNKHOUND_WATCH_PATHS, falling back to current directory"
            )
            return [Path.cwd()]

    # Default to current working directory
    current_dir = Path.cwd()
    if "CHUNKHOUND_DEBUG" in os.environ:
        import sys

        # print(
            # f"🔍 WATCHDOG: No CHUNKHOUND_WATCH_PATHS set, defaulting to current directory: {current_dir}",
            # file=sys.stderr,
        # )
        pass
    logging.info(
        f"FileWatcher: No CHUNKHOUND_WATCH_PATHS set, defaulting to current directory: {current_dir}"
    )
    return [current_dir]


def is_filesystem_watching_enabled() -> bool:
    """Check if filesystem watching is enabled via environment."""
    return os.environ.get("CHUNKHOUND_WATCH_ENABLED", "1").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class FileWatcherManager:
    """
    High-level manager for filesystem watching integration with MCP server.

    Handles the complete lifecycle including offline catch-up, live watching,
    and simple polling-based event processing.
    """

    def __init__(self):
        self.watcher: FileWatcher | None = None
        self.last_scan_time: float = time.time()
        self.watch_paths: list[Path] = []
        self.polling_task: asyncio.Task | None = None

    async def initialize(
        self,
        process_callback: Callable[[Path, str], Awaitable[None]],
        watch_paths: list[Path] | None = None,
    ) -> bool:
        """
        Initialize filesystem watching with offline catch-up.

        Args:
            process_callback: Function to call when files change
            watch_paths: Paths to watch (defaults to env config)

        Returns:
            True if successfully initialized, False otherwise
        """
        if not is_filesystem_watching_enabled():
            return False

        self.watch_paths = watch_paths or get_watch_paths_from_env()
        if not self.watch_paths:
            logging.error(
                "FileWatcherManager: No watch paths configured - filesystem monitoring disabled"
            )
            return False

        # Log the watch paths being monitored
        logging.info(
            f"FileWatcherManager: Initializing filesystem monitoring for {len(self.watch_paths)} paths:"
        )
        for i, path in enumerate(self.watch_paths):
            logging.info(f"  [{i + 1}] {path}")

        # Initialize without diagnostics in MCP mode
        pass

        try:
            # Perform offline catch-up scan with timeout to prevent MCP startup delays
            offline_changes = await scan_for_offline_changes(
                self.watch_paths,
                self.last_scan_time - 300,  # 5 minutes buffer
                timeout=3.0,  # 3 second timeout to prevent IDE timeouts
            )

            # Start filesystem watcher
            if WATCHDOG_AVAILABLE:
                self.watcher = FileWatcher(self.watch_paths)
                success = self.watcher.start()
                if not success:
                    logging.warning(
                        "FileWatcherManager: Failed to start filesystem watcher"
                    )
                    self.watcher = None  # Ensure watcher is None if start failed
            else:
                # Log warning when watchdog is unavailable
                import sys

                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                        # "⚠️  FileWatcherManager: watchdog library not available",
                        # file=sys.stderr,
                    # )
                    pass
                    # print("   File modification detection is DISABLED", file=sys.stderr)
                    # print("   Only initial file scanning will work", file=sys.stderr)
                self.watcher = None  # Ensure watcher is None if watchdog unavailable

            # Process offline changes immediately
            for change in offline_changes:
                try:
                    await process_callback(change.path, change.event_type)
                except Exception as e:
                    logging.error(
                        f"FileWatcherManager: Failed to process offline change {change}: {e}"
                    )

            # Start simple polling task
            self.polling_task = asyncio.create_task(
                self._polling_loop(process_callback)
            )

            return True

        except Exception as e:
            logging.error(
                f"FileWatcherManager: Failed to initialize filesystem monitoring: {e}"
            )
            await self.cleanup()
            return False

    async def _polling_loop(
        self, process_callback: Callable[[Path, str], Awaitable[None]]
    ):
        """Simple polling loop to process file change events."""
        logger.info("🔄 Polling loop started")
        loop_count = 0

        while True:
            try:
                # Get events from watcher if available
                if self.watcher:
                    events = self.watcher.get_events()
                    if events:
                        logger.info(f"📋 Processing {len(events)} events")
                        for event in events:
                            try:
                                await process_callback(event.path, event.event_type)
                            except Exception as e:
                                logger.error(f"❌ Failed to process event {event}: {e}")
                        logger.info("✅ Event processing batch completed")

                # Poll every 200ms - simple and responsive
                await asyncio.sleep(0.2)

                loop_count += 1
                if loop_count % 150 == 0:  # Log every 30 seconds (150 * 0.2s)
                    logger.info("🔄 Polling loop active")

            except asyncio.CancelledError:
                logger.info("🛑 Polling loop cancelled")
                break
            except Exception as e:
                # Continue polling even if individual batches fail
                logger.error(f"❌ Polling loop error: {e}")
                await asyncio.sleep(1.0)

    async def cleanup(self):
        """Clean up resources and stop filesystem watching."""
        # Cancel polling task
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass

        # Stop filesystem watcher
        if self.watcher:
            self.watcher.stop()

    def is_active(self) -> bool:
        """Check if filesystem watching is currently active."""
        return bool(
            self.watcher
            and self.watcher.is_available()
            and self.polling_task
            and not self.polling_task.done()
        )
