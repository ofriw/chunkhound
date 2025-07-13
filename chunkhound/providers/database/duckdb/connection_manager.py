"""DuckDB connection and schema management for ChunkHound."""

import os
from pathlib import Path
from typing import Any

# CRITICAL: Import numpy modules FIRST to prevent DuckDB threading segfaults
# This must happen before DuckDB operations start in threaded environments
# See: https://duckdb.org/docs/stable/clients/python/known_issues.html
try:
    import numpy

    # CRITICAL: Import numpy.core.multiarray specifically for threading safety
    # DuckDB docs: "If this module has not been imported from the main thread,
    # and a different thread during execution attempts to import it this causes
    # either a deadlock or a crash"
    import numpy.core.multiarray  # noqa: F401
except ImportError:
    # NumPy not available - VSS extension may not work properly
    pass

import duckdb
from loguru import logger


class DuckDBConnectionManager:
    """Manages DuckDB connections, schema creation, and database operations."""

    def __init__(self, db_path: Path | str, config: Any | None = None):
        """Initialize DuckDB connection manager.

        Args:
            db_path: Path to DuckDB database file or ":memory:" for in-memory database
            config: Database configuration for provider-specific settings
        """
        self._db_path = db_path
        self.connection: Any | None = None
        self.config = config

        # Note: Thread safety is now handled by DuckDBProvider's executor pattern
        # All database operations are serialized to a single thread

    @property
    def db_path(self) -> Path | str:
        """Database connection path or identifier."""
        return self._db_path

    @property
    def is_connected(self) -> bool:
        """Check if database connection is active.
        
        When using executor pattern, connection is managed by the executor thread.
        We consider it connected if initialization succeeded.
        """
        # With executor pattern, we don't maintain a connection here
        # Return True to indicate manager is initialized
        return True

    def connect(self) -> None:
        """Establish database connection and initialize schema with WAL validation."""
        logger.info(f"Connecting to DuckDB database: {self.db_path}")

        # Ensure parent directory exists for file-based databases
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if duckdb is None:
                raise ImportError("duckdb not available")

            # CRITICAL: Do NOT create connection here when using executor pattern
            # The executor will create its own thread-local connection
            # WAL handling has been moved to the executor's _create_connection method
            
            # Skip actual connection creation - executor will handle it
            logger.info("DuckDB connection manager initialized (connection deferred to executor)")

        except Exception as e:
            logger.error(f"DuckDB connection manager initialization failed: {e}")
            raise

    # WAL validation moved to DuckDBProvider._create_connection()

    # Method removed - MCP safety is now handled by executor pattern

    # WAL corruption detection moved to DuckDBProvider._is_wal_corruption_error()

    # WAL cleanup moved to DuckDBProvider._create_connection()

    # WAL corruption handling moved to DuckDBProvider._create_connection()

    def disconnect(self, skip_checkpoint: bool = False) -> None:
        """Close database connection with optional checkpointing.

        Args:
            skip_checkpoint: If True, skip the checkpoint operation (useful when
                           checkpoint was already done recently to avoid
                           checkpoint conflicts)
        """
        # With executor pattern, connection is managed by the executor
        # Nothing to do here since we don't maintain a connection
        if not os.environ.get("CHUNKHOUND_MCP_MODE"):
            logger.info("DuckDB connection manager disconnect (connection managed by executor)")

    def _load_extensions(self) -> None:
        """Load required DuckDB extensions with macOS x86 crash prevention."""
        logger.info("Loading DuckDB extensions")

        if self.connection is None:
            raise RuntimeError("No database connection")

        try:
            # Install and load VSS extension for vector operations
            self.connection.execute("INSTALL vss")
            self.connection.execute("LOAD vss")
            logger.info("VSS extension loaded successfully")

            # Enable experimental HNSW persistence AFTER VSS extension is loaded
            # This prevents segfaults when DuckDB tries to access vector functionality
            self.connection.execute("SET hnsw_enable_experimental_persistence = true")
            logger.debug("HNSW experimental persistence enabled")

        except Exception as e:
            logger.error(f"Failed to load DuckDB extensions: {e}")
            raise

    def health_check(self) -> dict[str, Any]:
        """Perform health check and return status information."""
        status = {
            "provider": "duckdb",
            "connected": self.is_connected,
            "db_path": str(self.db_path),
            "version": None,
            "extensions": [],
            "tables": [],
            "errors": [],
        }

        if not self.is_connected:
            status["errors"].append("Not connected to database")
            return status

        # With executor pattern, connection is managed by executor thread
        # Return basic status without accessing connection
        return status

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the database connection."""
        return {
            "provider": "duckdb",
            "db_path": str(self.db_path),
            "connected": self.is_connected,
            "memory_database": str(self.db_path) == ":memory:",
            "connection_type": "executor-managed",
        }
