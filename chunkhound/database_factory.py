"""Database factory module - creates Database instances with proper dependency injection.

This module eliminates circular dependencies by serving as a dedicated composition root
for Database creation. It imports both registry and database modules without creating
circular import chains.

UNIFIED DATABASE CREATION PATTERN:
1. ALL database instances must be created through create_database_with_dependencies()
2. NO direct Database() instantiation allowed in CLI or MCP code
3. Registry configuration happens automatically through this factory

BEHAVIOR GUARANTEE:
This factory ensures consistent component injection across all execution paths:
- CLI commands get same component setup as MCP servers
- All database instances have proper dependency injection
- Registry configuration is applied uniformly

INTEGRATION REQUIREMENT:
Any changes to this factory must be tested across all execution paths:
- CLI commands (chunkhound run)
- MCP stdio server
- MCP HTTP server
- File change processing

COMMON ISSUES:
- Direct Database() instantiation bypasses dependency injection
- Registry not configured before component creation
- Inconsistent component initialization across paths
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

    BEHAVIOR: Single source of truth for database creation across all execution paths
    PURPOSE: Eliminates duplicate initialization logic between CLI and MCP paths
    GUARANTEE: Ensures all database instances have proper dependency injection
    
    INITIALIZATION SEQUENCE:
    1. Configure registry before creating any components
    2. Create all service components through registry
    3. Inject all dependencies into Database constructor
    4. Return fully configured Database instance
    
    USED BY:
    - CLI commands (via args_to_config -> this factory)
    - MCP stdio server (via Config -> this factory)
    - MCP HTTP server (via Config -> this factory)
    - File change processing (indirectly via MCP server)
    
    CRITICAL REQUIREMENT:
    NEVER create Database() directly - always use this factory to ensure consistency
    
    COMMON ERRORS:
    - Direct Database() instantiation bypasses dependency injection
    - Registry not configured before component creation
    - Components created outside registry (inconsistent configuration)

    Args:
        db_path: Path to database file
        config: Registry configuration dictionary
        embedding_manager: Optional embedding manager

    Returns:
        Fully configured Database instance with injected dependencies
    """
    # Configure registry before creating any components
    # This step is mandatory - components depend on registry config
    configure_registry(config)

    # Create all service components through registry for consistency
    # This ensures all components use same configuration
    registry = get_registry()
    provider = registry.get_provider("database")
    indexing_coordinator = registry.create_indexing_coordinator()
    search_service = registry.create_search_service()
    embedding_service = registry.create_embedding_service()

    # Create Database with all dependencies injected
    # This bypasses legacy initialization and ensures consistency
    return Database(
        db_path=db_path,
        embedding_manager=embedding_manager,
        indexing_coordinator=indexing_coordinator,
        search_service=search_service,
        embedding_service=embedding_service,
        provider=provider,
    )
