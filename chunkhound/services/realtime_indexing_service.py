"""Real-time indexing service for MCP servers.

This service provides continuous filesystem monitoring and incremental updates
while maintaining search responsiveness. It leverages the existing indexing
infrastructure and respects the single-threaded database constraint.

Architecture:
- Single event queue for filesystem changes
- Background scan iterator for initial indexing
- No cancellation - operations complete naturally
- SerialDatabaseProvider handles all concurrency
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Iterator, Optional, Set

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from loguru import logger

from chunkhound.core.config.config import Config
from chunkhound.database_factory import DatabaseServices


def normalize_file_path(path: Path | str) -> str:
    """Single source of truth for path normalization across ChunkHound."""
    return str(Path(path).resolve())


class SimpleEventHandler(FileSystemEventHandler):
    """Simple sync event handler - no async complexity."""
    
    def __init__(self, event_queue: asyncio.Queue, config: Config | None = None, loop: asyncio.AbstractEventLoop | None = None):
        self.event_queue = event_queue
        self.config = config
        self.loop = loop
        
    def on_any_event(self, event: Any) -> None:
        """Handle filesystem events - simple queue operation."""
        if event.is_directory:
            return
            
        # Handle move events for atomic writes  
        if event.event_type == 'moved' and hasattr(event, 'dest_path'):
            self._handle_move_event(event.src_path, event.dest_path)
            return
        
        # Resolve path to canonical form to avoid /var vs /private/var issues
        file_path = Path(normalize_file_path(event.src_path))
        
        # Simple filtering for supported file types
        if not self._should_index(file_path):
            return
        
        # Put event in async queue from watchdog thread
        try:
            if self.loop and not self.loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.event_queue.put((event.event_type, file_path)), 
                    self.loop
                )
                future.result(timeout=1.0)  # Wait briefly for queue space
        except Exception as e:
            logger.warning(f"Failed to queue event for {file_path}: {e}")
            
    def _should_index(self, file_path: Path) -> bool:
        """Check if file should be indexed based on config patterns."""
        if not self.config:
            # Fallback to extension-based filtering if no config
            supported_extensions = {
                '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c',
                '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
                '.kt', '.scala', '.r', '.m', '.mm', '.md', '.txt'
            }
            return file_path.suffix.lower() in supported_extensions
        
        # Use config-based pattern matching
        from fnmatch import fnmatch
        
        file_str = str(file_path)
        file_name = file_path.name
        
        # Check exclude patterns first (more specific)
        for exclude_pattern in self.config.indexing.exclude:
            if fnmatch(file_str, exclude_pattern) or fnmatch(file_name, exclude_pattern):
                return False
        
        # Check include patterns  
        for include_pattern in self.config.indexing.include:
            if fnmatch(file_str, include_pattern) or fnmatch(file_name, include_pattern):
                return True
        
        return False
    
    def _handle_move_event(self, src_path: str, dest_path: str) -> None:
        """Handle atomic file moves (temp -> final file)."""
        src_file = Path(normalize_file_path(src_path))
        dest_file = Path(normalize_file_path(dest_path))
        
        # If moving FROM temp file TO supported file -> index destination
        if not self._should_index(src_file) and self._should_index(dest_file):
            logger.debug(f"Atomic write detected: {src_path} -> {dest_path}")
            self._queue_event('created', dest_file)
        
        # If moving FROM supported file -> handle as deletion + creation
        elif self._should_index(src_file) and self._should_index(dest_file):
            logger.debug(f"File rename: {src_path} -> {dest_path}")
            self._queue_event('deleted', src_file)
            self._queue_event('created', dest_file)
        
        # If moving FROM supported file TO temp/unsupported -> deletion
        elif self._should_index(src_file) and not self._should_index(dest_file):
            logger.debug(f"File moved to temp/unsupported: {src_path}")
            self._queue_event('deleted', src_file)
    
    def _queue_event(self, event_type: str, file_path: Path) -> None:
        """Queue an event for async processing."""
        try:
            if self.loop and not self.loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self.event_queue.put((event_type, file_path)), 
                    self.loop
                )
                future.result(timeout=1.0)
        except Exception as e:
            logger.warning(f"Failed to queue {event_type} event for {file_path}: {e}")


class RealtimeIndexingService:
    """Simple real-time indexing service with search responsiveness."""
    
    def __init__(self, services: DatabaseServices, config: Config):
        self.services = services
        self.config = config
        
        # Existing asyncio queue for priority processing
        self.file_queue: asyncio.Queue[tuple[str, Path]] = asyncio.Queue()
        
        # NEW: Async queue for events from watchdog (thread-safe via asyncio)
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Deduplication and error tracking
        self.pending_files: Set[Path] = set()
        self.failed_files: Set[str] = set()
        
        # Simple debouncing for rapid file changes
        self._pending_debounce: dict[str, float] = {}  # file_path -> timestamp
        self._debounce_delay = 0.5  # 500ms delay from research
        
        # Background scan state
        self.scan_iterator: Optional[Iterator] = None
        self.scan_complete = False
        
        # Filesystem monitoring
        self.observer: Optional[Any] = None
        self.event_handler: Optional[SimpleEventHandler] = None
        self.watch_path: Optional[Path] = None
        
        # Processing tasks
        self.process_task: Optional[asyncio.Task] = None
        self.event_consumer_task: Optional[asyncio.Task] = None
        
    async def start(self, watch_path: Path) -> None:
        """Start real-time indexing service."""
        logger.debug(f"Starting real-time indexing for {watch_path}")
        
        # Store the watch path
        self.watch_path = watch_path
        
        # Start filesystem monitoring with simple handler
        self._start_fs_monitor(watch_path)
        
        # Start event consumer (bridges thread-safe queue to asyncio)
        self.event_consumer_task = asyncio.create_task(self._consume_events())
        
        # Start processing loop
        self.process_task = asyncio.create_task(self._process_loop())
        
        # Initial scan is now handled by MCPServerBase to prevent blocking
        
    async def stop(self) -> None:
        """Stop the service gracefully."""
        logger.debug("Stopping real-time indexing service")
        
        # Stop filesystem observer
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
        # Cancel event consumer task
        if self.event_consumer_task:
            self.event_consumer_task.cancel()
            try:
                await self.event_consumer_task
            except asyncio.CancelledError:
                pass
                
        # Cancel processing task
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
                
    def _start_fs_monitor(self, watch_path: Path) -> None:
        """Start filesystem monitoring with simple handler."""
        self.event_handler = SimpleEventHandler(self.event_queue, self.config, asyncio.get_event_loop())
        
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(watch_path),
            recursive=True
        )
        self.observer.start()
        
        logger.debug(f"Started filesystem monitoring for {watch_path}")
        
    async def add_file(self, file_path: Path, priority: str = 'change') -> None:
        """Add file to processing queue with deduplication and debouncing."""
        if file_path not in self.pending_files:
            self.pending_files.add(file_path)
            
            # Simple debouncing for change events
            if priority == 'change':
                file_str = str(file_path)
                current_time = time.time()
                
                if file_str in self._pending_debounce:
                    # Update timestamp for existing pending file
                    self._pending_debounce[file_str] = current_time
                    return
                else:
                    # Schedule debounced processing
                    self._pending_debounce[file_str] = current_time
                    asyncio.create_task(self._debounced_add_file(file_path, priority))
            else:
                # Priority scan events bypass debouncing
                await self.file_queue.put((priority, file_path))
    
    async def _debounced_add_file(self, file_path: Path, priority: str) -> None:
        """Process file after debounce delay."""
        await asyncio.sleep(self._debounce_delay)
        
        file_str = str(file_path)
        if file_str in self._pending_debounce:
            last_update = self._pending_debounce[file_str]
            
            # Check if no recent updates during delay
            if time.time() - last_update >= self._debounce_delay:
                del self._pending_debounce[file_str]
                await self.file_queue.put((priority, file_path))
                logger.debug(f"Processing debounced file: {file_path}")
            
    async def _consume_events(self) -> None:
        """Simple event consumer - pure asyncio queue."""
        while True:
            try:
                # Get event from async queue with timeout
                try:
                    event_type, file_path = await asyncio.wait_for(
                        self.event_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Normal timeout, continue to check if task should stop
                    continue
                
                if event_type in ('created', 'modified'):
                    # Use existing add_file method for deduplication and priority
                    await self.add_file(file_path, priority='change')
                elif event_type == 'deleted':
                    # Handle deletion immediately
                    await self.remove_file(file_path)
                
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error consuming event: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
                
    async def remove_file(self, file_path: Path) -> None:
        """Remove file from database."""
        try:
            logger.debug(f"Removing file from database: {file_path}")
            self.services.provider.delete_file_completely(str(file_path))
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {e}")
            
    async def _process_loop(self) -> None:
        """Main processing loop - simple and robust."""
        logger.debug("Starting processing loop")
        
        while True:
            try:
                # Wait for next file (blocks if queue is empty)
                priority, file_path = await self.file_queue.get()
                
                # Remove from pending set
                self.pending_files.discard(file_path)
                
                # Check if file still exists (prevent race condition with deletion)
                if not file_path.exists():
                    logger.debug(f"Skipping {file_path} - file no longer exists")
                    continue
                
                # Process the file
                logger.debug(f"Processing {file_path} (priority: {priority})")
                
                # For initial scan, skip embeddings for speed
                skip_embeddings = (priority == 'initial')
                
                # Use existing indexing coordinator
                await self.services.indexing_coordinator.process_file(
                    file_path,
                    skip_embeddings=skip_embeddings
                )
                
                # Ensure database transaction is flushed for immediate visibility
                if hasattr(self.services.provider, 'flush'):
                    await self.services.provider.flush()
                
                # If we skipped embeddings, queue for embedding generation
                if skip_embeddings:
                    await self.add_file(file_path, priority='embed')
                    
            except asyncio.CancelledError:
                logger.debug("Processing loop cancelled")
                raise
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                # Track failed files for debugging and monitoring
                self.failed_files.add(str(file_path))
                # Continue processing other files
                
    async def get_stats(self) -> dict:
        """Get current service statistics."""
        return {
            'queue_size': self.file_queue.qsize(),
            'pending_files': len(self.pending_files),
            'failed_files': len(self.failed_files),
            'scan_complete': self.scan_complete,
            'observer_alive': self.observer.is_alive() if self.observer else False,
            'watching_directory': str(self.watch_path) if self.watch_path else None
        }