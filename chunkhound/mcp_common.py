"""Shared MCP server initialization logic.

This module provides common initialization patterns for both stdio and HTTP
MCP servers, ensuring consistent configuration validation and service setup.

The shared initialization pattern addresses:
- Config validation specific to MCP requirements
- Database and embedding service initialization
- Consistent error handling across server types

Architecture Note: MCP servers require global state due to the stdio protocol's
persistent connection model. This module helps manage that state consistently.
"""

import os
import sys
from pathlib import Path

try:
    from .core.config import EmbeddingProviderFactory
    from .core.config.config import Config
    from .database_factory import DatabaseServices, create_services
    from .embeddings import EmbeddingManager
except ImportError:
    from chunkhound.core.config import EmbeddingProviderFactory
    from chunkhound.core.config.config import Config
    from chunkhound.database_factory import DatabaseServices, create_services
    from chunkhound.embeddings import EmbeddingManager


def debug_log(message: str) -> None:
    """Log debug message to file if debug mode is enabled."""
    if os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes"):
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


async def initialize_mcp_services(
    config: Config, debug_mode: bool = False
) -> tuple[DatabaseServices, EmbeddingManager, Config]:
    """
    Initialize MCP services with validated configuration.

    This function assumes config is already validated.

    Args:
        config: Pre-validated config (required)
        debug_mode: Enable debug logging

    Returns:
        Tuple of (services, embedding_manager, config)

    Raises:
        ValueError: If required components cannot be initialized
    """
    # Get database path from config
    if not config.database or not config.database.path:
        raise ValueError("Database configuration not initialized")
    db_path = Path(config.database.path)

    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize embedding manager
    embedding_manager = EmbeddingManager()

    # Setup embedding provider (optional - continue if it fails)
    try:
        if config.embedding:
            provider = EmbeddingProviderFactory.create_provider(config.embedding)
            embedding_manager.register_provider(provider, set_default=True)
            if debug_mode:
                debug_log(f"Embedding provider registered: {config.embedding.provider}")
    except ValueError as e:
        # API key or configuration issue - expected for search-only usage
        if debug_mode:
            debug_log(f"Embedding provider setup skipped: {e}")
    except Exception as e:
        # Unexpected error - log but continue
        if debug_mode:
            debug_log(f"Unexpected error setting up embedding provider: {e}")

    # Create services using unified factory
    services = create_services(
        db_path=db_path,
        config=config.to_dict(),
        embedding_manager=embedding_manager,
    )

    # Connect to database
    services.provider.connect()

    return services, embedding_manager, config
