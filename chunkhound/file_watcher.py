#!/usr/bin/env python3
"""
Filesystem Event Watcher for ChunkHound MCP Server

Queue-based filesystem event monitoring with offline catch-up support.
Designed to prevent DuckDB WAL corruption by serializing all database operations
through the main MCP server thread.
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
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
                "data": data
            }

            with open(debug_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
                f.flush()
    except:
        pass  # Silent fail for MCP safety

# Import Language enum for centralized extension management
from core.types.common import Language

# Use centralized extension list from Language enum
SUPPORTED_EXTENSIONS = Language.get_all_extensions()
# Add special case filenames that are checked separately
SUPPORTED_FILENAMES = {'Makefile', 'makefile', 'GNUmakefile', 'gnumakefile'}

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
    """Filesystem event handler that queues events for processing."""

    def __init__(self, event_queue: asyncio.Queue, include_patterns: set[str] | None = None):
        super().__init__()
        debug_log("handler_init", event_queue_available=event_queue is not None,
                 include_patterns=list(include_patterns) if include_patterns else None)
        self.event_queue = event_queue
        self.include_patterns = include_patterns or SUPPORTED_EXTENSIONS


    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on extension and patterns."""
        # For deleted files, we can't check is_file() since they no longer exist
        # Check if it's a supported file using centralized logic
        return Language.is_supported_file(file_path)



    def _queue_event(self, path: Path, event_type: str, old_path: Path | None = None):
        """Queue a file change event if it passes filters and debouncing."""
        debug_log("queue_event_called", path=str(path), watchdog_event_type=event_type, queue_available=self.event_queue is not None)

        # Enhanced diagnostic logging for debugging
        import os
        import sys

        # ALWAYS log file events to stderr in debug mode to trace missing events
        if os.environ.get("CHUNKHOUND_DEBUG"):
            print("=== QUEUE EVENT ATTEMPT ===", file=sys.stderr)
            print(f"Path: {path}", file=sys.stderr)
            print(f"Event Type: {event_type}", file=sys.stderr)
            print(f"Queue Available: {self.event_queue is not None}", file=sys.stderr)
            print(f"File Exists: {path.exists()}", file=sys.stderr)
            print(f"File Extension: {path.suffix}", file=sys.stderr)

        if self.event_queue is None:
            logger.warning(f"TIMING: Event queue not initialized, skipping {event_type} {path}")
            debug_log("queue_event_no_queue", path=str(path))
            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("❌ EVENT QUEUE NOT INITIALIZED", file=sys.stderr)
                print("==========================", file=sys.stderr)
            return

        # For deletion events, always check extension pattern
        # For other events, also verify file exists
        if event_type != 'deleted' and not path.is_file():
            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("❌ FILE DOES NOT EXIST", file=sys.stderr)
                print("==========================", file=sys.stderr)
            return

        should_process = self._should_process_file(path)
        debug_log("should_process_check", path=str(path), should_process=should_process, file_suffix=path.suffix)

        if os.environ.get("CHUNKHOUND_DEBUG"):
            print(f"Should Process File: {should_process}", file=sys.stderr)
        if not should_process:
            debug_log("queue_event_rejected", path=str(path), reason="should_not_process")
            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("❌ FILE SHOULD NOT BE PROCESSED", file=sys.stderr)
                print("==========================", file=sys.stderr)
            return

        event_timestamp = time.time()

        event = FileChangeEvent(
            path=path,
            event_type=event_type,
            timestamp=event_timestamp,
            old_path=old_path
        )

        # Put event in queue (non-blocking)
        try:
            self.event_queue.put_nowait(event)
            logger.debug(f"TIMING: Event queued at {event_timestamp:.6f} - {event_type} {path}")
            debug_log("event_queued_success", path=str(path), watchdog_event_type=event_type, queue_size=self.event_queue.qsize())

            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("✅ EVENT SUCCESSFULLY QUEUED", file=sys.stderr)
                print(f"Queue Size After: {self.event_queue.qsize()}", file=sys.stderr)
                print("==========================", file=sys.stderr)
        except asyncio.QueueFull:
            # Queue is full, skip this event
            logger.warning(f"TIMING: Event queue full, skipping {event_type} {path} at {event_timestamp:.6f}")
            debug_log("event_queue_full", path=str(path), watchdog_event_type=event_type)

            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("❌ EVENT QUEUE FULL", file=sys.stderr)
                print("==========================", file=sys.stderr)

    def on_any_event(self, event):
        """Log all events for debugging - this should be called for EVERY event."""
        debug_log("on_any_event_called",
                 watchdog_event_type=event.event_type,
                 path=str(event.src_path),
                 is_directory=event.is_directory,
                 has_dest_path=hasattr(event, 'dest_path'))

    def on_modified(self, event):
        """Handle file modification events."""
        import os
        import sys
        
        # ALWAYS log watchdog events to stderr when debug is enabled
        if os.environ.get("CHUNKHOUND_DEBUG"):
            print(f"🔍 WATCHDOG on_modified: {event.src_path} (is_dir: {event.is_directory})", file=sys.stderr)
        
        debug_log("on_modified_called",
                 path=str(event.src_path),
                 is_directory=event.is_directory,
                 watchdog_event_type=getattr(event, 'event_type', 'unknown'))

        if not event.is_directory:
            path_str = str(event.src_path)
            logger.debug(f"TIMING: File modified detected at {time.time():.6f} - {event.src_path}")
            debug_log("on_modified_calling_queue", path=path_str, watchdog_event_type="modified")
            self._queue_event(Path(event.src_path), 'modified')

    def on_created(self, event):
        """Handle file creation events."""
        import os
        import sys
        
        # ALWAYS log watchdog events to stderr when debug is enabled
        if os.environ.get("CHUNKHOUND_DEBUG"):
            print(f"🔍 WATCHDOG on_created: {event.src_path} (is_dir: {event.is_directory})", file=sys.stderr)
        
        debug_log("on_created_called",
                 path=str(event.src_path),
                 is_directory=event.is_directory,
                 watchdog_event_type=getattr(event, 'event_type', 'unknown'))

        if not event.is_directory:
            path_str = str(event.src_path)
            debug_log("on_created_processing",
                     path=path_str,
                     file_exists=Path(path_str).exists())

            # Diagnostic logging for file creation debugging
            if os.environ.get("CHUNKHOUND_DEBUG"):
                print("=== FILE CREATION EVENT DETECTED ===", file=sys.stderr)
                print(f"File: {event.src_path}", file=sys.stderr)
                print(f"Timestamp: {time.time():.6f}", file=sys.stderr)
                print(f"Is Directory: {event.is_directory}", file=sys.stderr)
                print("====================================", file=sys.stderr)
            debug_log("on_created_calling_queue", path=path_str, watchdog_event_type="created")
            self._queue_event(Path(event.src_path), 'created')

    def on_moved(self, event):
        """Handle file move/rename events."""
        if not event.is_directory:
            old_path = Path(event.src_path)
            new_path = Path(event.dest_path)

            # Queue deletion of old path
            if self._should_process_file(old_path):
                self._queue_event(old_path, 'deleted')

            # Queue creation of new path
            self._queue_event(new_path, 'moved', old_path)

    def on_deleted(self, event):
        """Handle file deletion events."""
        debug_log("on_deleted_called", path=str(event.src_path), is_directory=event.is_directory)

        if not event.is_directory:
            logger.debug(f"TIMING: File deleted detected at {time.time():.6f} - {event.src_path}")
            debug_log("on_deleted_calling_queue", path=str(event.src_path), watchdog_event_type="deleted")
            self._queue_event(Path(event.src_path), 'deleted')


class FileWatcher:
    """
    Thread-safe filesystem watcher with queue-based event processing.

    Designed to work with DuckDB's single-process constraint by queuing
    filesystem events for processing by the main thread.
    """

    def __init__(self,
                 watch_paths: list[Path],
                 event_queue: asyncio.Queue,
                 include_patterns: set[str] | None = None):
        """
        Initialize the file watcher.

        Args:
            watch_paths: List of paths to watch for changes
            event_queue: Asyncio queue for communicating events to main thread
            include_patterns: File extensions to monitor (default: Python and Markdown)
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog package is required for filesystem watching")

        self.watch_paths = watch_paths
        self.event_queue = event_queue
        self.include_patterns = include_patterns or SUPPORTED_EXTENSIONS

        self.observer: Any | None = None
        self.event_handler = ChunkHoundEventHandler(event_queue, include_patterns)
        self.is_watching = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="FileWatcher")

    def start(self):
        """Start filesystem watching in a background thread."""
        if not WATCHDOG_AVAILABLE:
            # Improved error reporting for missing watchdog
            import sys
            if "CHUNKHOUND_DEBUG" in os.environ:
                print("⚠️  WATCHDOG UNAVAILABLE: File modification detection disabled", file=sys.stderr)
                print("   This means file changes will NOT be detected in real-time", file=sys.stderr)
                print("   Install watchdog: pip install watchdog", file=sys.stderr)
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
                            debug_log("scheduling_watch",
                                     path=str(watch_path),
                                     recursive=True,
                                     handler_methods=[m for m in dir(self.event_handler) if m.startswith('on_')])
                            self.observer.schedule(
                                self.event_handler,
                                str(watch_path),
                                recursive=True
                            )
                            debug_log("watch_scheduled", path=str(watch_path))

                if self.observer is not None:
                    debug_log("observer_starting",
                             watch_paths=[str(p) for p in self.watch_paths],
                             handler_type=type(self.event_handler).__name__)
                    self.observer.start()
                    self.is_watching = True
                    debug_log("observer_started", is_alive=self.observer.is_alive())
                    return True

            return False

        except Exception:
            # Silently fail - MCP server continues without filesystem watching
            return False

    def stop(self):
        """Stop filesystem watching and cleanup resources."""
        if self.observer and self.is_watching:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            except Exception:
                pass

        self.is_watching = False
        self.observer = None

        # Shutdown executor
        self.executor.shutdown(wait=True)

    def is_available(self) -> bool:
        """Check if filesystem watching is available and working."""
        return WATCHDOG_AVAILABLE and self.is_watching


async def scan_for_offline_changes(
    watch_paths: list[Path],
    last_scan_time: float,
    include_patterns: set[str] | None = None,
    timeout: float = 5.0
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
            for file_path in watch_path.rglob('*'):
                # Check timeout to prevent excessive MCP startup delays
                if time.time() - scan_start_time > timeout:
                    break

                if not should_process_file(file_path):
                    continue

                try:
                    # Check if file was modified after last scan
                    mtime = file_path.stat().st_mtime
                    if mtime > last_scan_time:
                        offline_changes.append(FileChangeEvent(
                            path=file_path,
                            event_type='modified',
                            timestamp=mtime
                        ))

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
        List of paths to watch, defaults to current working directory
    """
    paths_env = os.environ.get('CHUNKHOUND_WATCH_PATHS', '')

    if paths_env:
        logging.info(f"FileWatcher: Using CHUNKHOUND_WATCH_PATHS environment variable: {paths_env}")
        # Parse comma-separated paths
        path_strings = [p.strip() for p in paths_env.split(',') if p.strip()]
        paths = []

        for path_str in path_strings:
            try:
                path = Path(path_str).resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)
                    logging.info(f"FileWatcher: Added watch path: {path}")
                else:
                    logging.warning(f"FileWatcher: Skipping invalid watch path: {path_str}")
            except Exception as e:
                logging.warning(f"FileWatcher: Failed to resolve watch path '{path_str}': {e}")
                continue

        if paths:
            return paths
        else:
            logging.warning("FileWatcher: No valid paths from CHUNKHOUND_WATCH_PATHS, falling back to current directory")
            return [Path.cwd()]

    # Default to current working directory
    current_dir = Path.cwd()
    logging.info(f"FileWatcher: No CHUNKHOUND_WATCH_PATHS set, defaulting to current directory: {current_dir}")
    return [current_dir]


def is_filesystem_watching_enabled() -> bool:
    """Check if filesystem watching is enabled via environment."""
    return os.environ.get('CHUNKHOUND_WATCH_ENABLED', '1').lower() in ('1', 'true', 'yes', 'on')


async def process_file_change_queue(
    event_queue: asyncio.Queue,
    process_callback: Callable[[Path, str], Awaitable[None]],
    max_batch_size: int = 10
):
    """
    Process file change events from the queue.

    This function runs in the main thread to ensure single-threaded database access.

    Args:
        event_queue: Queue containing FileChangeEvent objects
        process_callback: Async function to call for each file change
        max_batch_size: Maximum number of events to process in one batch
    """
    logger.info(f"🔄 process_file_change_queue called - queue size: {event_queue.qsize()}")
    if os.environ.get("CHUNKHOUND_DEBUG"):
        print(f"DEBUG: process_file_change_queue called - queue size: {event_queue.qsize()}")
    batch = []

    try:
        logger.info("📥 Starting event collection from queue...")
        # Collect events up to batch size or until queue is empty
        while len(batch) < max_batch_size:
            try:
                event = event_queue.get_nowait()
                batch.append(event)
                logger.info(f"📥 Collected event {len(batch)}: {event.event_type} - {event.path}")
            except asyncio.QueueEmpty:
                logger.info(f"📥 Queue empty after collecting {len(batch)} events")
                break
            except Exception as e:
                logger.error(f"❌ Error collecting event from queue: {e}")
                break

        # Process collected events
        for event in batch:
            try:
                logger.info(f"Processing file change: {event.event_type} - {event.path}")
                await process_callback(event.path, event.event_type)
                logger.info(f"Successfully processed: {event.event_type} - {event.path}")
            except Exception as e:
                # Log error but continue processing other events
                logger.error(f"Failed to process file change: {event.event_type} - {event.path}: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            finally:
                event_queue.task_done()

    except Exception:
        # Ensure we mark tasks as done even if processing fails
        for _ in batch:
            try:
                event_queue.task_done()
            except ValueError:
                pass


class FileWatcherManager:
    """
    High-level manager for filesystem watching integration with MCP server.

    Handles the complete lifecycle including offline catch-up, live watching,
    and queue processing coordination.
    """

    def __init__(self):
        self.watcher: FileWatcher | None = None
        self.event_queue: asyncio.Queue | None = None
        self.last_scan_time: float = time.time()
        self.watch_paths: list[Path] = []
        self.processing_task: asyncio.Task | None = None

    async def initialize(self,
                        process_callback: Callable[[Path, str], Awaitable[None]],
                        watch_paths: list[Path] | None = None) -> bool:
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
            logging.error("FileWatcherManager: No watch paths configured - filesystem monitoring disabled")
            return False

        # Log the watch paths being monitored
        logging.info(f"FileWatcherManager: Initializing filesystem monitoring for {len(self.watch_paths)} paths:")
        for i, path in enumerate(self.watch_paths):
            logging.info(f"  [{i+1}] {path}")

        # Initialize without diagnostics in MCP mode
        pass

        try:
            # Create event queue
            self.event_queue = asyncio.Queue(maxsize=1000)

            # Perform offline catch-up scan with timeout to prevent MCP startup delays
            offline_changes = await scan_for_offline_changes(
                self.watch_paths,
                self.last_scan_time - 300,  # 5 minutes buffer
                timeout=3.0  # 3 second timeout to prevent IDE timeouts
            )
            # Queue offline changes for processing
            for change in offline_changes:
                try:
                    self.event_queue.put_nowait(change)
                except asyncio.QueueFull:
                    break

            # Start filesystem watcher
            if WATCHDOG_AVAILABLE:
                self.watcher = FileWatcher(self.watch_paths, self.event_queue)
                self.watcher.start()
            else:
                # Log warning when watchdog is unavailable
                import sys
                if "CHUNKHOUND_DEBUG" in os.environ:
                    print("⚠️  FileWatcherManager: watchdog library not available", file=sys.stderr)
                    print("   File modification detection is DISABLED", file=sys.stderr)
                    print("   Only initial file scanning will work", file=sys.stderr)

            # Start queue processing task
            self.processing_task = asyncio.create_task(
                self._queue_processing_loop(process_callback)
            )

            return True

        except Exception as e:
            logging.error(f"FileWatcherManager: Failed to initialize filesystem monitoring: {e}")
            await self.cleanup()
            return False

    async def _queue_processing_loop(self,
                                   process_callback: Callable[[Path, str], Awaitable[None]]):
        """Background task to process file change events."""
        logger.info("🔄 Queue processing loop started")
        loop_count = 0

        while True:
            try:
                # Process queue if items exist
                if self.event_queue and not self.event_queue.empty():
                    queue_size = self.event_queue.qsize()
                    logger.info(f"📋 Processing queue with {queue_size} events")
                    await process_file_change_queue(self.event_queue, process_callback)
                    logger.info("✅ Queue processing batch completed")
                
                # Use wait_for to allow checking for cancellation more responsively
                try:
                    await asyncio.wait_for(asyncio.sleep(1.0), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                
                loop_count += 1
                if loop_count % 30 == 0:  # Log every 30 seconds
                    queue_size = self.event_queue.qsize() if self.event_queue else 0
                    logger.info(f"🔄 Queue processing loop active - queue size: {queue_size}")

            except asyncio.CancelledError:
                logger.info("🛑 Queue processing loop cancelled")
                break
            except Exception as e:
                # Continue processing even if individual batches fail
                logger.error(f"❌ Queue processing loop error: {e}")
                try:
                    await asyncio.wait_for(asyncio.sleep(5.0), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    break

    async def cleanup(self):
        """Clean up resources and stop filesystem watching."""
        # Cancel processing task
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

        # Stop filesystem watcher
        if self.watcher:
            self.watcher.stop()

        # Clear queue
        if self.event_queue:
            while not self.event_queue.empty():
                try:
                    self.event_queue.get_nowait()
                    self.event_queue.task_done()
                except asyncio.QueueEmpty:
                    break

    def is_active(self) -> bool:
        """Check if filesystem watching is currently active."""
        return bool(self.watcher and self.watcher.is_available() and
                   self.processing_task and not self.processing_task.done())
