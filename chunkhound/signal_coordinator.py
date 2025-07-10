"""Signal-based coordination module for ChunkHound - Graceful database handoff between processes."""

import asyncio
import hashlib
import os
import signal
import time
from pathlib import Path
from typing import Any

from loguru import logger

from .process_detection import ProcessDetector


class SignalCoordinator:
    """Coordinate database access between MCP server and CLI processes using signals."""

    def __init__(self, db_path: Path, database_manager: Any) -> None:
        """Initialize signal coordinator.

        Args:
            db_path: Path to the database file
            database_manager: Database instance to coordinate
        """
        self.db_path = Path(db_path).resolve()
        self.database_manager = database_manager
        self.coordination_dir = self._get_coordination_dir()
        self.process_detector = ProcessDetector(self.db_path)

        # State tracking
        self._coordination_active = False
        self._shutdown_requested = False
        self._original_handlers: dict[int, Any] = {}
        self._original_db_path: Path | None = None

        # Ensure coordination directory exists
        self._ensure_coordination_dir()

    def _get_coordination_dir(self) -> Path:
        """Get coordination directory based on database path hash."""
        db_hash = hashlib.md5(str(self.db_path.absolute()).encode()).hexdigest()[:8]
        return Path(f"/tmp/chunkhound-{db_hash}")

    def _ensure_coordination_dir(self) -> None:
        """Ensure coordination directory exists."""
        try:
            self.coordination_dir.mkdir(parents=True, exist_ok=True)
            # Coordination directory ready (logging disabled for MCP/CLI compatibility)
            pass
        except OSError as e:
            # Failed to create coordination directory (logging disabled for MCP/CLI compatibility)
            pass
            raise

    def setup_mcp_signal_handling(self) -> None:
        """Setup signal handlers for MCP server process."""
        try:
            # Store original handlers for restoration
            self._original_handlers[signal.SIGUSR1] = signal.signal(
                signal.SIGUSR1, self._handle_shutdown_request
            )
            self._original_handlers[signal.SIGUSR2] = signal.signal(
                signal.SIGUSR2, self._handle_reopen_request
            )
            self._original_handlers[signal.SIGTERM] = signal.signal(
                signal.SIGTERM, self._handle_terminate
            )
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, self._handle_terminate
            )

            # Register this process as the MCP server
            self.process_detector.register_mcp_server(os.getpid())

            # Signal handling setup (logging disabled for MCP/CLI compatibility)
            pass

        except Exception as e:
            # Failed to setup signal handling (logging disabled for MCP/CLI compatibility)
            raise

    def setup_mcp_signal_handling_no_register(self) -> None:
        """Setup signal handlers for MCP server process without registering PID (already registered)."""
        try:
            # Store original handlers for restoration
            self._original_handlers[signal.SIGUSR1] = signal.signal(
                signal.SIGUSR1, self._handle_shutdown_request
            )
            self._original_handlers[signal.SIGUSR2] = signal.signal(
                signal.SIGUSR2, self._handle_reopen_request
            )
            self._original_handlers[signal.SIGTERM] = signal.signal(
                signal.SIGTERM, self._handle_terminate
            )
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, self._handle_terminate
            )

            # Skip registration since it was already done in server_lifespan
            # Signal handling setup (logging disabled for MCP/CLI compatibility)
            pass

        except Exception as e:
            # Failed to setup signal handling (logging disabled for MCP/CLI compatibility)
            raise

    def _handle_shutdown_request(self, signum: int, frame: Any) -> None:
        """Handle SIGUSR1 - request to shutdown database access."""
        # Received shutdown request (logging disabled for MCP/CLI compatibility)
        pass

        # Create async task for graceful shutdown
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._graceful_database_shutdown())
        except RuntimeError:
            # No event loop running, handle synchronously
            # No event loop available, handling shutdown synchronously (logging disabled for MCP/CLI compatibility)
            pass
            asyncio.run(self._graceful_database_shutdown())

    def _handle_reopen_request(self, signum: int, frame: Any) -> None:
        """Handle SIGUSR2 - request to reopen database access."""
        # Received reopen request (logging disabled for MCP/CLI compatibility)
        pass

        # Create async task for graceful reopen
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._graceful_database_reopen())
        except RuntimeError:
            # No event loop running, handle synchronously
            # No event loop available, handling reopen synchronously (logging disabled for MCP/CLI compatibility)
            pass
            asyncio.run(self._graceful_database_reopen())

    def _handle_terminate(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM/SIGINT - cleanup and exit."""
        logger.info(f"Received termination signal ({signum})")
        self._shutdown_requested = True

        # NOTE: Removed unsafe checkpoint operation from signal handler
        # Database operations in signal handlers can cause segfaults
        # The database will be properly closed in the normal shutdown flow

        # Cleanup coordination files
        self.cleanup_coordination_files()

        # Restore original signal handlers
        self._restore_signal_handlers()

        # Exit gracefully
        os._exit(0)

    async def _graceful_database_shutdown(self) -> None:
        """Gracefully shutdown database connection for handoff."""
        if self._coordination_active:
            logger.debug("Already in coordination mode, skipping shutdown")
            return

        self._coordination_active = True

        try:
            logger.info("Starting graceful database shutdown...")

            # Store original database path for restoration
            if self.database_manager and hasattr(self.database_manager, "db_path"):
                self._original_db_path = Path(self.database_manager.db_path)

            # Perform checkpoint before disconnect to minimize WAL size
            # This is safer now that it's done within the task context
            try:
                if hasattr(self.database_manager, "_execute_in_db_thread_sync"):
                    self.database_manager._execute_in_db_thread_sync(
                        "maybe_checkpoint", True
                    )
                    logger.info("Checkpoint completed before shutdown")
            except Exception as checkpoint_error:
                logger.warning(f"Checkpoint before shutdown failed: {checkpoint_error}")

            # Disconnect database connection (preferred method)
            if hasattr(self.database_manager, "disconnect"):
                if not self.database_manager.disconnect():
                    # If disconnect fails, try detach as fallback
                    logger.warning("Disconnect failed, attempting detach")
                    if hasattr(self.database_manager, "detach_database"):
                        if not self.database_manager.detach_database():
                            # If detach also fails, try complete close
                            logger.warning("Detach failed, attempting complete close")
                            if hasattr(self.database_manager, "close"):
                                self.database_manager.close()
                    elif hasattr(self.database_manager, "close"):
                        self.database_manager.close()
            elif hasattr(self.database_manager, "detach_database"):
                # Legacy fallback to detach if disconnect not available
                if not self.database_manager.detach_database():
                    # If detach fails, try complete close
                    logger.warning("Detach failed, attempting complete close")
                    if hasattr(self.database_manager, "close"):
                        self.database_manager.close()
            elif hasattr(self.database_manager, "close"):
                # Final fallback to close if neither disconnect nor detach available
                self.database_manager.close()

            logger.info("Database connection closed")

            # Signal ready for handoff
            ready_flag = self.coordination_dir / "ready.flag"
            ready_flag.write_text(str(time.time()))
            logger.info("Ready flag set - database available for indexing")

            # Wait for indexing completion
            await self._wait_for_indexing_completion()

        except Exception as e:
            logger.error(f"Error during database shutdown: {e}")
            # Ensure ready flag is cleared on error
            (self.coordination_dir / "ready.flag").unlink(missing_ok=True)
            self._coordination_active = False

    async def _graceful_database_reopen(self) -> None:
        """Gracefully reopen database connection after handoff."""
        if not self._coordination_active:
            logger.debug("Not in coordination mode, skipping reopen")
            return

        try:
            logger.info("Starting database reconnection...")

            # Reconnect to database (preferred method)
            if hasattr(self.database_manager, "reconnect"):
                if not self.database_manager.reconnect():
                    # If reconnect fails, try reattach as fallback
                    logger.warning("Reconnect failed, attempting reattach")
                    if hasattr(self.database_manager, "reattach_database"):
                        if not self.database_manager.reattach_database():
                            # If reattach also fails, try complete reconnect
                            logger.warning(
                                "Reattach failed, attempting complete reconnection"
                            )
                            if hasattr(self.database_manager, "connect"):
                                self.database_manager.connect()
                            elif self._original_db_path:
                                # Recreate database connection if needed
                                from .database import Database

                                self.database_manager = Database(self._original_db_path)
                                self.database_manager.connect()
                    elif hasattr(self.database_manager, "connect"):
                        self.database_manager.connect()
                    elif self._original_db_path:
                        # Recreate database connection if needed
                        from .database import Database

                        self.database_manager = Database(self._original_db_path)
                        self.database_manager.connect()
            elif hasattr(self.database_manager, "reattach_database"):
                # Legacy fallback to reattach if reconnect not available
                if not self.database_manager.reattach_database():
                    # If reattach fails, try complete reconnect
                    logger.warning("Reattach failed, attempting complete reconnection")
                    if hasattr(self.database_manager, "connect"):
                        self.database_manager.connect()
                    elif self._original_db_path:
                        # Recreate database connection if needed
                        from .database import Database

                        self.database_manager = Database(self._original_db_path)
                        self.database_manager.connect()
            elif hasattr(self.database_manager, "connect"):
                # Final fallback to connect if neither reconnect nor reattach available
                self.database_manager.connect()

            logger.info("Database connection restored")

            # Clear coordination flags
            (self.coordination_dir / "ready.flag").unlink(missing_ok=True)
            (self.coordination_dir / "done.flag").unlink(missing_ok=True)

            self._coordination_active = False
            logger.info("Database serving resumed")

        except Exception as e:
            logger.error(f"Error during database reopen: {e}")
            # Leave in coordination mode on error

    async def _wait_for_indexing_completion(self) -> None:
        """Wait for indexing operation to complete."""
        done_flag = self.coordination_dir / "done.flag"
        timeout = 300  # 5 minutes timeout
        start_time = time.time()

        logger.debug("Waiting for indexing completion...")

        while not done_flag.exists():
            if time.time() - start_time > timeout:
                logger.warning("Timeout waiting for indexing completion")
                break

            if self._shutdown_requested:
                logger.info("Shutdown requested during wait")
                break

            await asyncio.sleep(1)

        if done_flag.exists():
            logger.info("Indexing completion confirmed")
        else:
            logger.warning("Indexing completion not confirmed")

    def send_coordination_signal(
        self, signal_type: str, target_pid: int | None = None
    ) -> bool:
        """Send coordination signal to MCP server.

        Args:
            signal_type: 'shutdown' or 'reopen'
            target_pid: Optional PID to signal (auto-detected if None)

        Returns:
            True if signal sent successfully, False otherwise
        """
        if target_pid is None:
            target_pid = self.process_detector.get_server_pid()

        if target_pid is None:
            logger.error("No MCP server found to signal")
            return False

        try:
            if signal_type == "shutdown":
                os.kill(target_pid, signal.SIGUSR1)
                logger.info(f"Sent shutdown signal to PID {target_pid}")
            elif signal_type == "reopen":
                os.kill(target_pid, signal.SIGUSR2)
                logger.info(f"Sent reopen signal to PID {target_pid}")
            else:
                logger.error(f"Unknown signal type: {signal_type}")
                return False

            return True

        except (ProcessLookupError, PermissionError) as e:
            logger.error(
                f"Failed to send {signal_type} signal to PID {target_pid}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending signal: {e}")
            return False

    def wait_for_ready_flag(self, timeout: float = 10.0) -> bool:
        """Wait for ready flag to be set by MCP server.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready flag detected, False on timeout
        """
        ready_flag = self.coordination_dir / "ready.flag"
        start_time = time.time()

        logger.debug(f"Waiting for ready flag: {ready_flag}")

        while not ready_flag.exists():
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout waiting for ready flag after {timeout}s")
                return False

            time.sleep(0.1)

        logger.info("Ready flag detected - database available for access")
        return True

    def signal_indexing_complete(self) -> None:
        """Signal that indexing operation is complete."""
        done_flag = self.coordination_dir / "done.flag"
        try:
            done_flag.write_text(str(time.time()))
            logger.info("Indexing completion flag set")
        except Exception as e:
            logger.error(f"Failed to set completion flag: {e}")

    def cleanup_coordination_files(self) -> None:
        """Clean up coordination files and PID files."""
        try:
            # Clean up coordination flags
            for flag_file in ["ready.flag", "done.flag"]:
                flag_path = self.coordination_dir / flag_file
                flag_path.unlink(missing_ok=True)

            # Clean up through ProcessDetector
            self.process_detector.cleanup_coordination_files()

            logger.debug("Coordination files cleaned up")

        except Exception as e:
            logger.error(f"Error cleaning up coordination files: {e}")

    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        try:
            for sig, handler in self._original_handlers.items():
                if handler is not None:
                    signal.signal(sig, handler)

            self._original_handlers.clear()
            logger.debug("Signal handlers restored")

        except Exception as e:
            logger.error(f"Error restoring signal handlers: {e}")

    def is_coordination_active(self) -> bool:
        """Check if coordination is currently active."""
        return self._coordination_active

    def is_mcp_server_running(self) -> bool:
        """Check if MCP server is currently running."""
        return self.process_detector.is_mcp_server_running()

    def __enter__(self) -> "SignalCoordinator":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - cleanup resources."""
        self._restore_signal_handlers()
        self.cleanup_coordination_files()


class CLICoordinator:
    """Coordinate database access from CLI side."""

    def __init__(self, db_path: Path):
        """Initialize CLI coordinator.

        Args:
            db_path: Path to the database file
        """
        self.db_path = Path(db_path).resolve()
        self.signal_coordinator = SignalCoordinator(db_path, None)
        self._coordination_active = False

    def request_database_access(self, timeout: float = 10.0) -> bool:
        """Request database access from MCP server.

        Args:
            timeout: Maximum time to wait for handoff

        Returns:
            True if access granted, False otherwise
        """
        if not self.signal_coordinator.is_mcp_server_running():
            logger.debug("No MCP server running, no coordination needed")
            return True

        logger.info("Requesting database access from MCP server")

        # Send shutdown signal to MCP server
        if not self.signal_coordinator.send_coordination_signal("shutdown"):
            return False

        # Wait for ready flag
        if not self.signal_coordinator.wait_for_ready_flag(timeout):
            return False

        self._coordination_active = True
        logger.info("Database access granted")
        return True

    def release_database_access(self) -> bool:
        """Release database access back to MCP server.

        Returns:
            True if released successfully, False otherwise
        """
        if not self._coordination_active:
            logger.debug("No coordination active, nothing to release")
            return True

        logger.info("Releasing database access back to MCP server")

        # Signal indexing completion
        self.signal_coordinator.signal_indexing_complete()

        # Send reopen signal to MCP server
        success = self.signal_coordinator.send_coordination_signal("reopen")

        # Clean up coordination files
        self.signal_coordinator.cleanup_coordination_files()

        self._coordination_active = False

        if success:
            logger.info("Database access released")
        else:
            logger.warning("Failed to release database access")

        return success

    def __enter__(self) -> "CLICoordinator":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensure cleanup."""
        if self._coordination_active:
            self.release_database_access()
