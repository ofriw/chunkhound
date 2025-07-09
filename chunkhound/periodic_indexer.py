#!/usr/bin/env python3
"""
Periodic Indexing Manager for ChunkHound MCP Server
Provides background periodic indexing to maintain database consistency.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

from .task_coordinator import TaskCoordinator, TaskPriority


class PeriodicIndexManager:
    """Manages background periodic indexing with lowest priority."""

    def __init__(
        self,
        indexing_coordinator,
        task_coordinator: TaskCoordinator,
        base_directory: Path,
        interval: int = 300,  # 5 minutes default
        batch_size: int = 10,
        enabled: bool = True,
    ):
        """Initialize periodic index manager.

        Args:
            indexing_coordinator: IndexingCoordinator instance for file processing
            task_coordinator: TaskCoordinator for priority-based execution
            base_directory: Base directory to scan for changes
            interval: Scan interval in seconds (default: 300)
            batch_size: Files per batch (default: 10)
            enabled: Whether periodic indexing is enabled (default: True)
        """
        self._indexing_coordinator = indexing_coordinator
        self._task_coordinator = task_coordinator
        self._base_directory = base_directory
        self._interval = interval
        self._batch_size = batch_size
        self._enabled = enabled

        # State tracking
        self._scanning_task: asyncio.Task | None = None
        self._optimization_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._scan_position = 0
        self._last_scan_time = 0
        self._scan_start_counter = 0  # Count scan start attempts
        self._current_scan_start_time = 0  # Track when current scan started
        self._last_optimization_time = 0  # Track last optimization time
        self._quiet_period_minutes = 5  # 5 minutes of inactivity before optimization

        # Statistics
        self._stats = {
            "scans_completed": 0,
            "files_processed": 0,
            "files_updated": 0,
            "files_skipped": 0,
            "last_scan_duration": 0,
            "optimizations_performed": 0,
        }

    @classmethod
    def from_environment(
        cls,
        indexing_coordinator,
        task_coordinator: TaskCoordinator,
        base_directory: Path | None = None,
    ) -> "PeriodicIndexManager":
        """Create periodic index manager from environment variables.

        Environment Variables:
            CHUNKHOUND_PERIODIC_INDEX_INTERVAL: Scan interval in seconds (default: 300)
            CHUNKHOUND_PERIODIC_BATCH_SIZE: Files per batch (default: 10)
            CHUNKHOUND_PERIODIC_INDEX_ENABLED: Enable/disable (default: true)
            CHUNKHOUND_WATCH_PATHS: Paths to watch (defaults to project root)

        Args:
            indexing_coordinator: IndexingCoordinator instance
            task_coordinator: TaskCoordinator instance
            base_directory: Base directory to scan (defaults to same logic as FileWatcherManager)

        Returns:
            Configured PeriodicIndexManager instance
        """
        # TODO: Add periodic indexing configuration to centralized Config class
        # For now, keep using environment variables as these are specialized settings
        # that are mainly used in subprocess/service contexts
        interval = int(os.getenv("CHUNKHOUND_PERIODIC_INDEX_INTERVAL", "300"))
        batch_size = int(os.getenv("CHUNKHOUND_PERIODIC_BATCH_SIZE", "10"))
        enabled = (
            os.getenv("CHUNKHOUND_PERIODIC_INDEX_ENABLED", "true").lower() == "true"
        )

        # Use the same path resolution logic as FileWatcherManager
        if base_directory is None:
            try:
                from .utils.project_detection import get_project_watch_paths
                watch_paths = get_project_watch_paths()
                base_directory = watch_paths[0] if watch_paths else Path.cwd()
            except ImportError:
                # Fallback to environment variable check
                paths_env = os.environ.get("CHUNKHOUND_WATCH_PATHS", "")
                if paths_env:
                    path_strings = [p.strip() for p in paths_env.split(",") if p.strip()]
                    if path_strings:
                        base_directory = Path(path_strings[0]).resolve()
                    else:
                        base_directory = Path.cwd()
                else:
                    base_directory = Path.cwd()

        return cls(
            indexing_coordinator=indexing_coordinator,
            task_coordinator=task_coordinator,
            base_directory=base_directory,
            interval=interval,
            batch_size=batch_size,
            enabled=enabled,
        )

    async def start(self) -> None:
        """Start periodic indexing tasks."""
        if not self._enabled or self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start immediate background scan to catch changes since last offline index
        self._scanning_task = asyncio.create_task(self._periodic_scan_loop())
        
        # Start optimization task to handle quiet period optimization
        self._optimization_task = asyncio.create_task(self._periodic_optimization_loop())

        # Debug output only in debug mode to avoid disrupting JSON-RPC
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print(
            #     f"PeriodicIndexManager started - interval: {self._interval}s, batch_size: {self._batch_size}",
            #     file=sys.stderr,
            # )
            pass

    async def stop(self, timeout: float = 30.0) -> None:
        """Stop periodic indexing tasks.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self._running:
            return

        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("PeriodicIndexManager stopping...", file=sys.stderr)
            pass
        self._running = False
        self._shutdown_event.set()

        # Stop scanning task
        if self._scanning_task:
            try:
                await asyncio.wait_for(self._scanning_task, timeout=timeout/2)
            except asyncio.TimeoutError:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     "PeriodicIndexManager scan task did not stop gracefully, cancelling",
                    #     file=sys.stderr,
                    # )
                    pass
                self._scanning_task.cancel()
                try:
                    await self._scanning_task
                except asyncio.CancelledError:
                    pass
        
        # Stop optimization task
        if self._optimization_task:
            try:
                await asyncio.wait_for(self._optimization_task, timeout=timeout/2)
            except asyncio.TimeoutError:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     "PeriodicIndexManager optimization task did not stop gracefully, cancelling",
                    #     file=sys.stderr,
                    # )
                    pass
                self._optimization_task.cancel()
                try:
                    await self._optimization_task
                except asyncio.CancelledError:
                    pass

        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("PeriodicIndexManager stopped", file=sys.stderr)

            pass
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about periodic indexing."""
        return {
            **self._stats,
            "enabled": self._enabled,
            "running": self._running,
            "interval": self._interval,
            "batch_size": self._batch_size,
            "scan_position": self._scan_position,
            "last_scan_time": self._last_scan_time,
        }

    async def _cancel_running_scan_safely(self) -> None:
        """Cancel any running background scan tasks safely without disrupting other tasks."""
        # Implementation follows asyncio best practices from web search
        # Only cancels background scan tasks, not other tasks in the queue
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("Attempting to cancel long-running background scan", file=sys.stderr)

            pass
        # The TaskCoordinator handles individual task cancellation gracefully
        # We don't need to manually cancel since the scan will naturally complete
        # and the counter reset will prevent new overlapping scans

    async def _periodic_scan_loop(self) -> None:
        """Main periodic scanning loop."""
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("PeriodicIndexManager scan loop started", file=sys.stderr)

            pass
        # Immediate startup scan to catch changes since last offline index
        if self._running:
            await self._queue_background_scan("startup")

        # Continue with periodic scans
        while self._running:
            try:
                # Wait for interval or shutdown signal
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self._interval
                    )
                    # Shutdown signal received
                    break
                except asyncio.TimeoutError:
                    # Timeout reached, time for next scan
                    pass

                if self._running:
                    # Check if we should skip this scan cycle due to long-running previous scan
                    current_time = time.time()
                    scan_duration = (
                        current_time - self._current_scan_start_time
                        if self._current_scan_start_time > 0
                        else 0
                    )
                    max_scan_duration = self._interval * 2  # 2 cycles

                    if (
                        self._scan_start_counter > 0
                        and scan_duration < max_scan_duration
                    ):
                        # Previous scan still running and within acceptable time - skip this cycle
                        if "CHUNKHOUND_DEBUG" in os.environ:
                            # print(
                            #     f"Skipping scan cycle - previous scan still running ({scan_duration:.1f}s, "
                            #     f"counter: {self._scan_start_counter})",
                            #     file=sys.stderr,
                            # )
                            pass
                        continue
                    elif (
                        self._scan_start_counter > 0
                        and scan_duration >= max_scan_duration
                    ):
                        # Previous scan running too long - reset and restart
                        if "CHUNKHOUND_DEBUG" in os.environ:
                            # print(
                            #     f"Background scan running too long ({scan_duration:.1f}s > {max_scan_duration}s), "
                            #     f"resetting counters (was attempt #{self._scan_start_counter})",
                            #     file=sys.stderr,
                            # )

                            pass
                        # Reset counters - the long-running scan will eventually complete and see the reset
                        self._scan_start_counter = 0
                        self._current_scan_start_time = 0

                    # Only start new scan if no scan is currently running
                    if self._scan_start_counter == 0:
                        await self._queue_background_scan("periodic")

            except Exception as e:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(f"Error in periodic scan loop: {e}", file=sys.stderr)
                    pass
                # Continue running despite errors
                await asyncio.sleep(5)  # Brief recovery delay

        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("PeriodicIndexManager scan loop stopped", file=sys.stderr)

            pass
    async def _queue_background_scan(self, scan_type: str) -> None:
        """Queue a background directory scan.

        Args:
            scan_type: Type of scan ("startup" or "periodic")
        """
        try:
            if not self._task_coordinator:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     "No task coordinator available for background scan",
                    #     file=sys.stderr,
                    # )
                    pass
                return

            # Increment scan start counter to track overlapping scans
            self._scan_start_counter += 1
            self._current_scan_start_time = time.time()

            # Queue background scan task with lowest priority
            await self._task_coordinator.queue_task_nowait(
                TaskPriority.BACKGROUND, self._execute_background_scan, scan_type
            )

            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(
                #     f"Queued {scan_type} background scan (attempt #{self._scan_start_counter})",
                #     file=sys.stderr,
                # )

                pass
        except Exception as e:
            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(f"Failed to queue background scan: {e}", file=sys.stderr)
                pass
            # Reset counter on queue failure
            if self._scan_start_counter > 0:
                self._scan_start_counter -= 1

    async def _execute_background_scan(self, scan_type: str) -> None:
        """Execute a background directory scan in small batches.

        Args:
            scan_type: Type of scan ("startup" or "periodic")
        """
        scan_start_time = time.time()
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print(f"Starting {scan_type} background scan", file=sys.stderr)

            pass
        try:
            # Discover all files in base directory
            # Get patterns and exclude patterns from unified config
            from chunkhound.core.config.unified_config import ChunkHoundConfig

            config = ChunkHoundConfig.load_hierarchical(
                project_dir=self._base_directory
            )
            exclude_patterns = config.indexing.get_effective_exclude_patterns(
                self._base_directory
            )
            files = self._indexing_coordinator._discover_files(
                self._base_directory,
                patterns=config.indexing.include_patterns,  # Use config layer patterns
                exclude_patterns=exclude_patterns,
            )

            if not files:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print("No files found during background scan", file=sys.stderr)
                    pass
                return

            # Clean up orphaned files (same as chunkhound index)
            if scan_type == "startup":
                cleaned_files = self._indexing_coordinator._cleanup_orphaned_files(
                    self._base_directory, files, exclude_patterns
                )
                if cleaned_files > 0 and "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     f"Cleaned up {cleaned_files} orphaned files during startup scan",
                    #     file=sys.stderr,
                    # )

                    pass
            # Reset scan position for startup scans, continue from position for periodic
            if scan_type == "startup":
                self._scan_position = 0

            # Process files in small batches starting from scan position
            batch_count = 0
            files_in_this_scan = 0

            while self._scan_position < len(files) and self._running:
                # Get next batch of files
                batch_end = min(self._scan_position + self._batch_size, len(files))
                batch_files = files[self._scan_position : batch_end]

                # Process batch
                await self._process_file_batch(batch_files)

                # Update position and stats
                self._scan_position = batch_end
                batch_count += 1
                files_in_this_scan += len(batch_files)

                # Yield control between batches to allow higher priority tasks
                await asyncio.sleep(0.1)  # 100ms yield

            # Reset position when we reach the end
            if self._scan_position >= len(files):
                self._scan_position = 0

            # Update statistics and reset scan tracking
            scan_duration = time.time() - scan_start_time
            self._stats["scans_completed"] += 1
            self._stats["last_scan_duration"] = scan_duration
            self._last_scan_time = scan_start_time

            # Reset scan tracking counters on successful completion
            self._scan_start_counter = 0
            self._current_scan_start_time = 0

            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(
                #     f"Completed {scan_type} background scan: "
                #     f"{files_in_this_scan} files in {batch_count} batches, "
                #     f"duration: {scan_duration:.2f}s",
                #     file=sys.stderr,
                # )

                pass
            # Force checkpoint after background scan to minimize WAL size
            try:
                # Get database provider from registry
                from .registry import get_registry

                database_provider = get_registry().get_provider("database")
                if database_provider and hasattr(
                    database_provider, "_maybe_checkpoint"
                ):
                    database_provider._maybe_checkpoint(force=True)
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        # print(
                        #     f"Checkpoint completed after {scan_type} background scan",
                        #     file=sys.stderr,
                        # )
                        pass
            except Exception as checkpoint_error:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     f"Checkpoint after background scan failed: {checkpoint_error}",
                    #     file=sys.stderr,
                    # )

                    pass
        except asyncio.CancelledError:
            # Handle graceful cancellation - don't log as error
            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(
                #     f"Background scan was cancelled (scan_type: {scan_type})",
                #     file=sys.stderr,
                # )
                pass
            # Reset counters on cancellation
            self._scan_start_counter = 0
            self._current_scan_start_time = 0
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            if "CHUNKHOUND_DEBUG" in os.environ:
                # print(f"Background scan failed: {e}", file=sys.stderr)
                pass
            # Reset counters on error
            self._scan_start_counter = 0
            self._current_scan_start_time = 0

    async def _process_file_batch(self, files: list[Path]) -> None:
        """Process a batch of files for background indexing.

        Args:
            files: List of file paths to process
        """
        for file_path in files:
            if not self._running:
                break

            try:
                # Use existing process_file method for consistent processing
                result = await self._indexing_coordinator.process_file(
                    file_path,
                    skip_embeddings=True,  # Skip embeddings for background processing
                )

                # Update statistics
                self._stats["files_processed"] += 1

                if result["status"] == "success":
                    self._stats["files_updated"] += 1
                elif result["status"] == "up_to_date":
                    self._stats["files_skipped"] += 1

            except Exception as e:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(
                    #     f"Error processing file {file_path} in background: {e}",
                    #     file=sys.stderr,
                    # )
                    pass
                # Continue with next file despite errors
    
    async def _periodic_optimization_loop(self) -> None:
        """Periodic loop to check for quiet periods and run database optimization."""
        if "CHUNKHOUND_DEBUG" in os.environ:
            # print("PeriodicIndexManager optimization loop started", file=sys.stderr)
            pass
        
        while self._running:
            try:
                # Wait for 60 seconds between checks
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=60
                    )
                    # Shutdown signal received
                    break
                except asyncio.TimeoutError:
                    # Timeout - continue with quiet period check
                    pass
                
                # Get database provider from registry
                try:
                    from .registry import get_registry
                    
                    database_provider = get_registry().get_provider("database")
                    if not database_provider:
                        continue
                        
                    # Check if we have the last_activity_time property
                    if not hasattr(database_provider, "last_activity_time"):
                        continue
                    
                    # Get last activity time
                    last_activity = database_provider.last_activity_time
                    if last_activity is None:
                        continue
                    
                    # Check if it's been quiet for the specified period
                    current_time = time.time()
                    quiet_duration = current_time - last_activity
                    quiet_period_seconds = self._quiet_period_minutes * 60
                    
                    if quiet_duration >= quiet_period_seconds:
                        # Check if we haven't optimized recently (avoid repeated optimizations)
                        time_since_last_optimization = current_time - self._last_optimization_time
                        if time_since_last_optimization >= quiet_period_seconds:
                            if "CHUNKHOUND_DEBUG" in os.environ:
                                # print(
                                #     f"Database quiet for {quiet_duration:.1f}s, running optimization",
                                #     file=sys.stderr,
                                # )
                                pass
                            
                            # Run optimization
                            try:
                                database_provider.optimize_tables()
                                self._last_optimization_time = current_time
                                self._stats["optimizations_performed"] += 1
                                
                                if "CHUNKHOUND_DEBUG" in os.environ:
                                    # print(
                                    #     "Database optimization completed successfully",
                                    #     file=sys.stderr,
                                    # )
                                    pass
                            except Exception as opt_error:
                                if "CHUNKHOUND_DEBUG" in os.environ:
                                    # print(
                                    #     f"Database optimization failed: {opt_error}",
                                    #     file=sys.stderr,
                                    # )
                                    pass
                    
                except Exception as e:
                    if "CHUNKHOUND_DEBUG" in os.environ:
                        # print(
                        #     f"Error in optimization check: {e}",
                        #     file=sys.stderr,
                        # )
                        pass
                        
            except asyncio.CancelledError:
                # Handle graceful cancellation
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print("Optimization loop was cancelled", file=sys.stderr)
                    pass
                break
            except Exception as e:
                if "CHUNKHOUND_DEBUG" in os.environ:
                    # print(f"Unexpected error in optimization loop: {e}", file=sys.stderr)
                    pass
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait before retrying
