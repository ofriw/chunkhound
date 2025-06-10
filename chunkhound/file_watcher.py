#!/usr/bin/env python3
"""
Filesystem Event Watcher for ChunkHound MCP Server

Queue-based filesystem event monitoring with offline catch-up support.
Designed to prevent DuckDB WAL corruption by serializing all database operations
through the main MCP server thread.
"""

import os
import asyncio
import time
from pathlib import Path
from typing import Optional, Set, Dict, List, Callable, Awaitable, Any, Protocol
from dataclasses import dataclass

from concurrent.futures import ThreadPoolExecutor
import logging

# Protocol for event handlers
class EventHandlerProtocol(Protocol):
    def on_modified(self, event: Any) -> None: ...
    def on_created(self, event: Any) -> None: ...
    def on_moved(self, event: Any) -> None: ...
    def on_deleted(self, event: Any) -> None: ...

# Handle conditional imports for watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler  # type: ignore
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
    old_path: Optional[Path] = None  # For move events


class ChunkHoundEventHandler(FileSystemEventHandler):
    """Filesystem event handler that queues events for processing."""
    
    def __init__(self, event_queue: asyncio.Queue, include_patterns: Optional[Set[str]] = None):
        super().__init__()
        self.event_queue = event_queue
        self.include_patterns = include_patterns or {'.py', '.pyw', '.md', '.markdown'}
        self.last_events: Dict[str, float] = {}
        self.debounce_delay = 2.0  # 2-second debounce
    
    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on extension and patterns."""
        if not file_path.is_file():
            return False
        
        suffix = file_path.suffix.lower()
        return suffix in self.include_patterns
    
    def _debounce_event(self, file_path: str) -> bool:
        """Check if event should be processed based on debouncing logic."""
        now = time.time()
        last_time = self.last_events.get(file_path, 0)
        
        if now - last_time < self.debounce_delay:
            return False
        
        self.last_events[file_path] = now
        return True
    
    def _queue_event(self, path: Path, event_type: str, old_path: Optional[Path] = None):
        """Queue a file change event if it passes filters and debouncing."""
        if not self._should_process_file(path):
            return
        
        path_str = str(path)
        if not self._debounce_event(path_str):
            return
        
        event = FileChangeEvent(
            path=path,
            event_type=event_type,
            timestamp=time.time(),
            old_path=old_path
        )
        
        # Put event in queue (non-blocking)
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Queue is full, skip this event
            pass
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            self._queue_event(Path(event.src_path), 'modified')
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
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
        if not event.is_directory:
            self._queue_event(Path(event.src_path), 'deleted')


class FileWatcher:
    """
    Thread-safe filesystem watcher with queue-based event processing.
    
    Designed to work with DuckDB's single-process constraint by queuing
    filesystem events for processing by the main thread.
    """
    
    def __init__(self, 
                 watch_paths: List[Path],
                 event_queue: asyncio.Queue,
                 include_patterns: Optional[Set[str]] = None):
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
        self.include_patterns = include_patterns or {'.py', '.pyw', '.md', '.markdown'}
        
        self.observer: Optional[Any] = None
        self.event_handler = ChunkHoundEventHandler(event_queue, include_patterns)
        self.is_watching = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="FileWatcher")
    
    def start(self):
        """Start filesystem watching in a background thread."""
        if not WATCHDOG_AVAILABLE:
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
                            self.observer.schedule(
                                self.event_handler,
                                str(watch_path),
                                recursive=True
                            )
                
                if self.observer is not None:
                    self.observer.start()
                    self.is_watching = True
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
    watch_paths: List[Path],
    last_scan_time: float,
    include_patterns: Optional[Set[str]] = None
) -> List[FileChangeEvent]:
    """
    Scan for files that changed while the server was offline.
    
    Args:
        watch_paths: Paths to scan for changes
        last_scan_time: Timestamp of last scan (files modified after this will be included)
        include_patterns: File extensions to include
    
    Returns:
        List of FileChangeEvent objects for modified files
    """
    if include_patterns is None:
        include_patterns = {'.py', '.pyw', '.md', '.markdown'}
    
    offline_changes = []
    
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
                except (OSError, IOError):
                    # Skip files that can't be accessed
                    continue
        
        except Exception:
            # Skip directories that can't be accessed
            continue
    
    return offline_changes


def get_watch_paths_from_env() -> List[Path]:
    """
    Get watch paths from environment configuration.
    
    Returns:
        List of paths to watch, defaults to current working directory
    """
    paths_env = os.environ.get('CHUNKHOUND_WATCH_PATHS', '')
    
    if paths_env:
        # Parse comma-separated paths
        path_strings = [p.strip() for p in paths_env.split(',') if p.strip()]
        paths = []
        
        for path_str in path_strings:
            try:
                path = Path(path_str).resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)
            except Exception:
                continue
        
        return paths if paths else [Path.cwd()]
    
    # Default to current working directory
    return [Path.cwd()]


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
    batch = []
    
    try:
        # Collect events up to batch size or until queue is empty
        while len(batch) < max_batch_size:
            try:
                event = event_queue.get_nowait()
                batch.append(event)
            except asyncio.QueueEmpty:
                break
        
        # Process collected events
        for event in batch:
            try:
                await process_callback(event.path, event.event_type)
            except Exception:
                # Log error but continue processing other events
                # (In production, might want to send to error monitoring)
                pass
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
        self.watcher: Optional[FileWatcher] = None
        self.event_queue: Optional[asyncio.Queue] = None
        self.last_scan_time: float = time.time()
        self.watch_paths: List[Path] = []
        self.processing_task: Optional[asyncio.Task] = None
    
    async def initialize(self, 
                        process_callback: Callable[[Path, str], Awaitable[None]],
                        watch_paths: Optional[List[Path]] = None) -> bool:
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
            return False

        try:
            # Create event queue
            self.event_queue = asyncio.Queue(maxsize=1000)
            
            # Perform offline catch-up scan
            offline_changes = await scan_for_offline_changes(
                self.watch_paths,
                self.last_scan_time - 300  # 5 minutes buffer
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
            
            # Start queue processing task
            self.processing_task = asyncio.create_task(
                self._queue_processing_loop(process_callback)
            )
            
            return True
            
        except Exception:
            await self.cleanup()
            return False
    
    async def _queue_processing_loop(self, 
                                   process_callback: Callable[[Path, str], Awaitable[None]]):
        """Background task to process file change events."""
        while True:
            try:
                # Wait for events and process them in batches
                await asyncio.sleep(1.0)  # Process every second
                
                if self.event_queue and not self.event_queue.empty():
                    await process_file_change_queue(self.event_queue, process_callback)
                
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue processing even if individual batches fail
                await asyncio.sleep(5.0)  # Back off on errors
    
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