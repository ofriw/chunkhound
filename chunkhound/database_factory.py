"""Database factory module - creates Database instances with proper dependency injection.

This module eliminates circular dependencies by serving as a dedicated composition root
for Database creation. It imports both registry and database modules without creating
circular import chains.
"""

from pathlib import Path
from typing import Any

from chunkhound.database import Database
from chunkhound.embeddings import EmbeddingManager
from chunkhound.registry import configure_registry, get_registry


def create_database_with_dependencies(
    db_path: Path | str,
    config: dict[str, Any],
    embedding_manager: EmbeddingManager | None = None,
) -> Database:
    """Create a Database instance with all dependencies properly injected.

    This is the unified factory function that eliminates the duplicate responsibility
    issue between CLI and MCP paths. Both should use this instead of Database.__init__().

    Args:
        db_path: Path to database file
        config: Registry configuration dictionary
        embedding_manager: Optional embedding manager

    Returns:
        Fully configured Database instance with injected dependencies
    """
    # Configure registry first
    configure_registry(config)

    # Create all service components through registry
    registry = get_registry()
    provider = registry.get_provider("database")
    indexing_coordinator = registry.create_indexing_coordinator()
    search_service = registry.create_search_service()
    embedding_service = registry.create_embedding_service()

    # Create Database with dependency injection (bypasses legacy initialization)
    return Database(
        db_path=db_path,
        embedding_manager=embedding_manager,
        indexing_coordinator=indexing_coordinator,
        search_service=search_service,
        embedding_service=embedding_service,
        provider=provider,
    )
