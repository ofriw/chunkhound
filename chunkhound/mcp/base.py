"""Base class for MCP servers providing common initialization and lifecycle management.

This module provides a base class that handles:
- Service initialization (database, embeddings)
- Configuration validation
- Lifecycle management (startup/shutdown)
- Common error handling patterns

Architecture Note: Both stdio and HTTP servers inherit from this base
to ensure consistent initialization while respecting protocol-specific constraints.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from chunkhound.core.config import EmbeddingProviderFactory
from chunkhound.core.config.config import Config
from chunkhound.database_factory import DatabaseServices, create_services
from chunkhound.embeddings import EmbeddingManager
from chunkhound.services.directory_indexing_service import DirectoryIndexingService
from chunkhound.services.realtime_indexing_service import RealtimeIndexingService


class MCPServerBase(ABC):
    """Base class for MCP server implementations.

    Provides common initialization, configuration validation, and lifecycle
    management for both stdio and HTTP server variants.

    Subclasses must implement:
    - _register_tools(): Register protocol-specific tool handlers
    - run(): Main server execution loop
    """

    def __init__(self, config: Config, debug_mode: bool = False, args: Any = None):
        """Initialize base MCP server.

        Args:
            config: Validated configuration object
            debug_mode: Enable debug logging to stderr
            args: Original CLI arguments for direct path access
        """
        self.config = config
        self.args = args  # Store original CLI args for direct path access
        self.debug_mode = debug_mode or os.getenv("CHUNKHOUND_DEBUG", "").lower() in (
            "true",
            "1",
            "yes",
        )

        # Service components - initialized lazily or eagerly based on subclass
        self.services: DatabaseServices | None = None
        self.embedding_manager: EmbeddingManager | None = None
        self.realtime_indexing: RealtimeIndexingService | None = None

        # Initialization state
        self._initialized = False
        self._init_lock = asyncio.Lock()

        # Set MCP mode to suppress stderr output that interferes with JSON-RPC
        os.environ["CHUNKHOUND_MCP_MODE"] = "1"

    def debug_log(self, message: str) -> None:
        """Log debug message to file if debug mode is enabled."""
        if self.debug_mode:
            # Write to debug file instead of stderr to preserve JSON-RPC protocol
            debug_file = os.getenv("CHUNKHOUND_DEBUG_FILE", "/tmp/chunkhound_mcp_debug.log")
            try:
                with open(debug_file, "a") as f:
                    from datetime import datetime
                    timestamp = datetime.now().isoformat()
                    f.write(f"[{timestamp}] [MCP] {message}\n")
                    f.flush()
            except Exception:
                # Silently fail if we can't write to debug file
                pass

    async def initialize(self) -> None:
        """Initialize services and database connection.

        This method is idempotent - safe to call multiple times.
        Uses locking to ensure thread-safe initialization.

        Raises:
            ValueError: If required configuration is missing
            Exception: If services fail to initialize
        """
        async with self._init_lock:
            if self._initialized:
                return

            self.debug_log("Starting service initialization")

            # Validate database configuration
            if not self.config.database or not self.config.database.path:
                raise ValueError("Database configuration not initialized")

            db_path = Path(self.config.database.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Initialize embedding manager
            self.embedding_manager = EmbeddingManager()

            # Setup embedding provider (optional - continue if it fails)
            try:
                if self.config.embedding:
                    provider = EmbeddingProviderFactory.create_provider(
                        self.config.embedding
                    )
                    self.embedding_manager.register_provider(provider, set_default=True)
                    self.debug_log(
                        f"Embedding provider registered: {self.config.embedding.provider}"
                    )
            except ValueError as e:
                # API key or configuration issue - expected for search-only usage
                self.debug_log(f"Embedding provider setup skipped: {e}")
            except Exception as e:
                # Unexpected error - log but continue
                self.debug_log(f"Unexpected error setting up embedding provider: {e}")

            # Create services using unified factory
            self.services = create_services(
                db_path=db_path,
                config=self.config,
                embedding_manager=self.embedding_manager,
            )

            # Connect to database
            self.services.provider.connect()

            # Perform initial directory scan using shared service
            self.debug_log("Starting initial directory scan")
            indexing_service = DirectoryIndexingService(
                indexing_coordinator=self.services.indexing_coordinator,
                config=self.config,
                progress_callback=self.debug_log
            )

            # Use direct path like CLI indexer - align path resolution
            if self.args and hasattr(self.args, 'path'):
                target_path = Path(self.args.path)
                self.debug_log(f"Using direct path from args: {target_path}")
            else:
                # Fallback to config resolution (shouldn't happen in normal usage)
                target_path = getattr(self.config, '_target_dir', None) or db_path.parent.parent
                self.debug_log(f"Using fallback path resolution: {target_path}")

            stats = await indexing_service.process_directory(target_path, no_embeddings=False)

            self.debug_log(f"Initial scan completed: {stats.files_processed} files, {stats.chunks_created} chunks")

            # Start real-time indexing service
            self.debug_log("Starting real-time indexing service")
            self.realtime_indexing = RealtimeIndexingService(self.services, self.config)

            # Use same path for watching
            await self.realtime_indexing.start(target_path)

            self._initialized = True

            self.debug_log("Service initialization complete")

    async def cleanup(self) -> None:
        """Clean up resources and close database connection.

        This method is idempotent - safe to call multiple times.
        """
        # Stop real-time indexing first
        if self.realtime_indexing:
            self.debug_log("Stopping real-time indexing service")
            await self.realtime_indexing.stop()

        if self.services and self.services.provider.is_connected:
            self.debug_log("Closing database connection")
            self.services.provider.disconnect()
            self._initialized = False

    def ensure_services(self) -> DatabaseServices:
        """Ensure services are initialized and return them.

        Returns:
            DatabaseServices instance

        Raises:
            RuntimeError: If services are not initialized
        """
        if not self.services:
            raise RuntimeError("Services not initialized. Call initialize() first.")

        # Ensure database connection is active
        if not self.services.provider.is_connected:
            self.services.provider.connect()

        return self.services

    def ensure_embedding_manager(self) -> EmbeddingManager:
        """Ensure embedding manager is available and has providers.

        Returns:
            EmbeddingManager instance

        Raises:
            RuntimeError: If no embedding providers are available
        """
        if not self.embedding_manager or not self.embedding_manager.list_providers():
            raise RuntimeError(
                "No embedding providers available. Configure an embedding provider "
                "in .chunkhound.json or set CHUNKHOUND_EMBEDDING__API_KEY environment variable."
            )
        return self.embedding_manager

    @abstractmethod
    def _register_tools(self) -> None:
        """Register tools with the server implementation.

        Subclasses must implement this to register tools using their
        protocol-specific decorators/patterns.
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """Run the server.

        Subclasses must implement their protocol-specific server loop.
        """
        pass
