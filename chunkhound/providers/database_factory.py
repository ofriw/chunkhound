"""Database provider factory for ChunkHound."""

from pathlib import Path
from typing import TYPE_CHECKING

from chunkhound.core.config.unified_config import DatabaseConfig
from chunkhound.embeddings import EmbeddingManager
from interfaces.database_provider import DatabaseProvider

if TYPE_CHECKING:
    from providers.database.duckdb_provider import DuckDBProvider
    from providers.database.lancedb_provider import LanceDBProvider


class DatabaseProviderFactory:
    """Factory for creating database provider instances based on configuration."""
    
    @staticmethod
    def create_provider(
        config: DatabaseConfig,
        embedding_manager: EmbeddingManager | None = None
    ) -> DatabaseProvider:
        """Create database provider instance based on configuration.
        
        Args:
            config: Database configuration
            embedding_manager: Optional embedding manager
            
        Returns:
            Database provider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        db_path = Path(config.path)
        
        if config.provider == 'duckdb':
            from providers.database.duckdb_provider import DuckDBProvider
            return DuckDBProvider(db_path, embedding_manager, config=config)
        elif config.provider == 'lancedb':
            from providers.database.lancedb_provider import LanceDBProvider
            return LanceDBProvider(db_path, embedding_manager, config=config)
        else:
            raise ValueError(f"Unsupported database provider: {config.provider}")