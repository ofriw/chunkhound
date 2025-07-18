"""
Unified configuration system for ChunkHound - Backward compatibility wrapper.

This module provides backward compatibility for the ChunkHoundConfig class
by wrapping the new centralized Config system. The actual configuration logic
is now in chunkhound.core.config.config.Config.

This wrapper maintains the existing API while delegating to the new system.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Import configuration components from the new modular system
from .config import Config
from .database_config import DatabaseConfig
from .embedding_config import EmbeddingConfig
from .indexing_config import IndexingConfig
from .mcp_config import MCPConfig


class ChunkHoundConfig(BaseSettings):
    """
    Unified configuration for ChunkHound - Backward compatibility wrapper.
    
    This class wraps the new Config class to maintain backward compatibility
    while delegating all actual configuration logic to the centralized system.
    
    Configuration Sources (in order of precedence):
    1. CLI arguments (highest priority)
    2. Config file (via --config path)
    3. Environment variables (CHUNKHOUND_*)
    4. Default values (lowest priority)

    Environment Variable Examples:
        CHUNKHOUND_EMBEDDING__PROVIDER=openai
        CHUNKHOUND_EMBEDDING__API_KEY=sk-...
        CHUNKHOUND_EMBEDDING__MODEL=text-embedding-3-small
        CHUNKHOUND_MCP__TRANSPORT=http
        CHUNKHOUND_MCP__PORT=3001
        CHUNKHOUND_INDEXING__WATCH=true
        CHUNKHOUND_DATABASE__PATH=custom.db
        CHUNKHOUND_DEBUG=true
    """

    model_config = SettingsConfigDict(
        env_prefix="CHUNKHOUND_",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",
        env_file=None,  # Disable automatic .env loading
    )

    # Internal config instance that does the actual work
    _config: Config | None = None

    def __init__(self, **data: Any):
        """Initialize the wrapper with a Config instance."""
        # Initialize BaseSettings first
        super().__init__(**data)
        
        # Import here to avoid circular imports
        from chunkhound.utils.project_detection import find_project_root
        
        # If we're being initialized with component configs, create a Config instance
        if any(key in data for key in ["embedding", "mcp", "indexing", "database", "debug"]):
            # Create Config instance from the provided data with project root
            project_root = find_project_root()
            self._config = Config(target_dir=project_root, **data)
        else:
            # Create default Config instance with project root to detect .chunkhound.json
            project_root = find_project_root()
            self._config = Config(target_dir=project_root)
    
    @property
    def embedding(self) -> Optional[EmbeddingConfig]:
        """Get embedding configuration."""
        return self._config.embedding if self._config else None
    
    @property
    def mcp(self) -> MCPConfig:
        """Get MCP configuration."""
        return self._config.mcp if self._config else MCPConfig()
    
    @property
    def indexing(self) -> IndexingConfig:
        """Get indexing configuration."""
        return self._config.indexing if self._config else IndexingConfig()
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._config.database if self._config else DatabaseConfig()
    
    @property
    def debug(self) -> bool:
        """Get debug flag."""
        return self._config.debug if self._config else False

    @classmethod
    def load_hierarchical(
        cls, config_file: Path | None = None, **override_values: Any
    ) -> "ChunkHoundConfig":
        """
        Load configuration from hierarchical sources.

        Args:
            config_file: Explicit configuration file path (via --config)
            **override_values: Runtime parameter overrides

        Returns:
            Loaded and validated configuration
        """
        # Use the new Config class to handle loading
        config = Config(config_file=config_file, overrides=override_values)
        
        # Create wrapper instance
        instance = cls()
        instance._config = config
        return instance


    def get_missing_config(self) -> list[str]:
        """
        Get list of missing required configuration parameters.

        Returns:
            List of missing configuration parameter names
        """
        # Delegate to the EmbeddingConfig's validation method
        missing = []

        # Get embedding configuration issues
        embedding_missing = self.embedding.get_missing_config()
        for item in embedding_missing:
            missing.append(f"embedding.{item}")

        return missing

    def is_fully_configured(self) -> bool:
        """
        Check if all required configuration is present.

        Returns:
            True if fully configured, False otherwise
        """
        return self.embedding.is_provider_configured()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert configuration to dictionary format.

        Returns:
            Configuration as dictionary
        """
        if self._config:
            return self._config.to_dict()
        # Return default structure if no config
        return {
            "embedding": self.embedding.model_dump(),
            "mcp": self.mcp.model_dump(),
            "indexing": self.indexing.model_dump(),
            "database": self.database.model_dump(),
            "debug": self.debug
        }

    def save_to_file(self, file_path: Path) -> None:
        """
        Save configuration to JSON file.

        Args:
            file_path: Path to save configuration file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        config_dict = self.to_dict()

        with open(file_path, "w") as f:
            json.dump(config_dict, f, indent=2)

    def get_embedding_model(self) -> str:
        """Get the embedding model name with provider defaults."""
        return self.embedding.get_default_model()

    def __repr__(self) -> str:
        """String representation hiding sensitive information."""
        api_key_display = "***" if self.embedding.api_key else None
        return (
            f"ChunkHoundConfig("
            f"embedding.provider={self.embedding.provider}, "
            f"embedding.model={self.get_embedding_model()}, "
            f"embedding.api_key={api_key_display}, "
            f"mcp.transport={self.mcp.transport}, "
            f"database.path={self.database.path})"
        )
    
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Dump model to dictionary for backward compatibility."""
        return self.to_dict()

    @classmethod
    def get_default_exclude_patterns(cls) -> list[str]:
        """Get the default exclude patterns for file indexing.

        Returns:
            List of default exclude patterns
        """
        # Create a temporary instance to get the default patterns
        temp_config = IndexingConfig()
        return temp_config.exclude


# Global configuration instance
_config_instance: ChunkHoundConfig | None = None


def get_config() -> ChunkHoundConfig:
    """
    Get the global configuration instance.

    Returns:
        Global ChunkHoundConfig instance
    """
    global _config_instance
    if _config_instance is None:
        # Create wrapper instance with default Config
        _config_instance = ChunkHoundConfig()
    return _config_instance


def set_config(config: ChunkHoundConfig) -> None:
    """
    Set the global configuration instance.

    Args:
        config: Configuration instance to set as global
    """
    global _config_instance
    _config_instance = config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _config_instance
    _config_instance = None
