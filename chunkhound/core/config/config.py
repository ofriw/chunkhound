"""Centralized configuration management for ChunkHound.

This module provides a unified configuration system with clear precedence:
1. CLI arguments (highest priority)
2. Local .chunkhound.json in target directory (if present)
3. Config file (via --config path)
4. Environment variables
5. Default values (lowest priority)
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .database_config import DatabaseConfig
from .embedding_config import EmbeddingConfig
from .indexing_config import IndexingConfig
from .mcp_config import MCPConfig


class Config(BaseModel):
    """Centralized configuration for ChunkHound."""

    model_config = ConfigDict(validate_assignment=True)

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig | None = Field(default=None)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    debug: bool = Field(default=False)

    def __init__(self, args: Any | None = None, **kwargs: Any) -> None:
        """Universal configuration initialization that handles all contexts.

        Automatically applies correct precedence order:
        1. CLI arguments (highest priority)
        2. Environment variables
        3. Config file (via --config path, env var, or local .chunkhound.json)
        4. Default values (lowest priority)

        Args:
            args: Optional argparse.Namespace from command line parsing
            **kwargs: Direct overrides for testing or special cases
        """
        # Start with defaults
        config_data: dict[str, Any] = {}

        # 1. Smart config file resolution (before env vars)
        config_file = None
        target_dir = None

        # Extract config file and target directory from args if provided
        if args:
            # Get config file from --config if present
            if hasattr(args, "config") and args.config:
                config_file = Path(args.config)

            # Get target directory from args.path for local config detection
            if hasattr(args, "path") and args.path:
                target_dir = Path(args.path)

        # If no config file from args, check environment variable
        if not config_file:
            env_config_file = os.getenv("CHUNKHOUND_CONFIG_FILE")
            if env_config_file:
                config_file = Path(env_config_file)

        # Always detect project root for local config detection
        if target_dir is None:
            from chunkhound.utils.project_detection import find_project_root

            target_dir = find_project_root()

        # Store target_dir for use in validation
        self._target_dir = target_dir

        # 2. Load config file if found
        if config_file and config_file.exists():
            import json

            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                    self._deep_merge(config_data, file_config)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in config file {config_file}: {e}. "
                    "Please check the file format and try again."
                )

        # 3. Check for local .chunkhound.json in target directory
        if target_dir and target_dir.exists():
            local_config_path = target_dir / ".chunkhound.json"
            if local_config_path.exists() and local_config_path != config_file:
                import json

                try:
                    with open(local_config_path) as f:
                        local_config = json.load(f)
                        self._deep_merge(config_data, local_config)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON in config file {local_config_path}: {e}. "
                        "Please check the file format and try again."
                    )

        # 4. Load environment variables (override config files)
        env_vars = self._load_env_vars()
        self._deep_merge(config_data, env_vars)

        # 5. Apply CLI arguments (highest precedence)
        if args:
            cli_overrides = self._extract_cli_overrides(args)
            self._deep_merge(config_data, cli_overrides)

        # 6. Apply any direct kwargs (for testing)
        if kwargs:
            self._deep_merge(config_data, kwargs)

        # Special handling for EmbeddingConfig
        if "embedding" in config_data and isinstance(config_data["embedding"], dict):
            # Create EmbeddingConfig instance with the data
            config_data["embedding"] = EmbeddingConfig(**config_data["embedding"])

        # Initialize the model
        super().__init__(**config_data)

    def _load_env_vars(self) -> dict[str, Any]:
        """Load configuration from environment variables.

        Supports both legacy and new environment variable names.
        Uses CHUNKHOUND_ prefix with __ delimiter for nested values.
        """
        config: dict[str, Any] = {}

        # Debug mode
        if os.getenv("CHUNKHOUND_DEBUG"):
            config["debug"] = os.getenv("CHUNKHOUND_DEBUG", "").lower() in (
                "true",
                "1",
                "yes",
            )

        # Database configuration
        # Support both old and new environment variable names
        if db_path := (
            os.getenv("CHUNKHOUND_DATABASE__PATH") or os.getenv("CHUNKHOUND_DB_PATH")
        ):
            config.setdefault("database", {})["path"] = db_path
        if db_provider := os.getenv("CHUNKHOUND_DATABASE__PROVIDER"):
            config.setdefault("database", {})["provider"] = db_provider
        if index_type := os.getenv("CHUNKHOUND_DATABASE__LANCEDB_INDEX_TYPE"):
            config.setdefault("database", {})["lancedb_index_type"] = index_type

        # Embedding configuration
        embedding_config: dict[str, Any] = {}

        # New embedding env vars
        if api_key := os.getenv("CHUNKHOUND_EMBEDDING__API_KEY"):
            embedding_config["api_key"] = api_key
        if base_url := os.getenv("CHUNKHOUND_EMBEDDING__BASE_URL"):
            embedding_config["base_url"] = base_url

        # New embedding env vars
        if provider := os.getenv("CHUNKHOUND_EMBEDDING__PROVIDER"):
            embedding_config["provider"] = provider
        if model := os.getenv("CHUNKHOUND_EMBEDDING__MODEL"):
            embedding_config["model"] = model
        if batch_size := os.getenv("CHUNKHOUND_EMBEDDING__BATCH_SIZE"):
            embedding_config["batch_size"] = int(batch_size)
        if max_concurrent := os.getenv("CHUNKHOUND_EMBEDDING__MAX_CONCURRENT_BATCHES"):
            embedding_config["max_concurrent_batches"] = int(max_concurrent)

        if embedding_config:
            config["embedding"] = embedding_config

        # MCP configuration
        mcp_config: dict[str, Any] = {}
        if transport := os.getenv("CHUNKHOUND_MCP__TRANSPORT"):
            mcp_config["transport"] = transport
        if port := os.getenv("CHUNKHOUND_MCP__PORT"):
            mcp_config["port"] = int(port)
        if host := os.getenv("CHUNKHOUND_MCP__HOST"):
            mcp_config["host"] = host
        if cors := os.getenv("CHUNKHOUND_MCP__CORS"):
            mcp_config["cors"] = cors.lower() in ("true", "1", "yes")

        if mcp_config:
            config["mcp"] = mcp_config

        # Indexing configuration
        indexing_config: dict[str, Any] = {}
        if batch_size := os.getenv("CHUNKHOUND_INDEXING__BATCH_SIZE"):
            indexing_config["batch_size"] = int(batch_size)
        if db_batch_size := os.getenv("CHUNKHOUND_INDEXING__DB_BATCH_SIZE"):
            indexing_config["db_batch_size"] = int(db_batch_size)
        if max_concurrent := os.getenv("CHUNKHOUND_INDEXING__MAX_CONCURRENT"):
            indexing_config["max_concurrent"] = int(max_concurrent)
        if force_reindex := os.getenv("CHUNKHOUND_INDEXING__FORCE_REINDEX"):
            indexing_config["force_reindex"] = force_reindex.lower() in (
                "true",
                "1",
                "yes",
            )
        if cleanup := os.getenv("CHUNKHOUND_INDEXING__CLEANUP"):
            indexing_config["cleanup"] = cleanup.lower() in ("true", "1", "yes")
        if ignore_gitignore := os.getenv("CHUNKHOUND_INDEXING__IGNORE_GITIGNORE"):
            indexing_config["ignore_gitignore"] = ignore_gitignore.lower() in (
                "true",
                "1",
                "yes",
            )

        # Include/exclude patterns
        if include := os.getenv("CHUNKHOUND_INDEXING__INCLUDE"):
            indexing_config["include"] = include.split(",")
        if exclude := os.getenv("CHUNKHOUND_INDEXING__EXCLUDE"):
            indexing_config["exclude"] = exclude.split(",")

        if indexing_config:
            config["indexing"] = indexing_config

        return config

    def _extract_cli_overrides(self, args: Any) -> dict[str, Any]:
        """Extract configuration overrides from CLI arguments.

        Args:
            args: Parsed command line arguments

        Returns:
            Dictionary of configuration overrides
        """
        overrides: dict[str, Any] = {}

        # Database arguments
        if hasattr(args, "db") and args.db:
            overrides.setdefault("database", {})["path"] = args.db
        if hasattr(args, "database_provider") and args.database_provider:
            overrides.setdefault("database", {})["provider"] = args.database_provider
        if (
            hasattr(args, "database_lancedb_index_type")
            and args.database_lancedb_index_type
        ):
            overrides.setdefault("database", {})["lancedb_index_type"] = (
                args.database_lancedb_index_type
            )

        # Embedding arguments
        if hasattr(args, "provider") and args.provider:
            overrides.setdefault("embedding", {})["provider"] = args.provider
        if hasattr(args, "model") and args.model:
            overrides.setdefault("embedding", {})["model"] = args.model
        if hasattr(args, "api_key") and args.api_key:
            overrides.setdefault("embedding", {})["api_key"] = args.api_key
        if hasattr(args, "base_url") and args.base_url:
            overrides.setdefault("embedding", {})["base_url"] = args.base_url
        if hasattr(args, "embedding_batch_size") and args.embedding_batch_size:
            overrides.setdefault("embedding", {})["batch_size"] = (
                args.embedding_batch_size
            )
        if hasattr(args, "embedding_max_concurrent") and args.embedding_max_concurrent:
            overrides.setdefault("embedding", {})["max_concurrent"] = (
                args.embedding_max_concurrent
            )

        # MCP arguments
        if hasattr(args, "http") and args.http:
            overrides.setdefault("mcp", {})["transport"] = "http"
        elif hasattr(args, "stdio") and hasattr(args, "http") and not args.http:
            overrides.setdefault("mcp", {})["transport"] = "stdio"
        if hasattr(args, "port") and args.port:
            overrides.setdefault("mcp", {})["port"] = args.port
        if hasattr(args, "host") and args.host:
            overrides.setdefault("mcp", {})["host"] = args.host
        if hasattr(args, "cors") and args.cors:
            overrides.setdefault("mcp", {})["cors"] = args.cors

        # Indexing arguments
        if hasattr(args, "batch_size") and args.batch_size:
            overrides.setdefault("indexing", {})["batch_size"] = args.batch_size
        if hasattr(args, "db_batch_size") and args.db_batch_size:
            overrides.setdefault("indexing", {})["db_batch_size"] = args.db_batch_size
        if hasattr(args, "max_concurrent") and args.max_concurrent:
            overrides.setdefault("indexing", {})["max_concurrent"] = args.max_concurrent
        if hasattr(args, "force_reindex") and args.force_reindex:
            overrides.setdefault("indexing", {})["force_reindex"] = args.force_reindex
        if hasattr(args, "cleanup") and args.cleanup:
            overrides.setdefault("indexing", {})["cleanup"] = args.cleanup
        if (
            hasattr(args, "indexing_ignore_gitignore")
            and args.indexing_ignore_gitignore
        ):
            overrides.setdefault("indexing", {})["ignore_gitignore"] = (
                args.indexing_ignore_gitignore
            )

        # Include/exclude patterns
        if hasattr(args, "include") and args.include:
            overrides.setdefault("indexing", {})["include"] = args.include
        if hasattr(args, "exclude") and args.exclude:
            overrides.setdefault("indexing", {})["exclude"] = args.exclude

        # Debug flag
        if hasattr(args, "debug") and args.debug:
            overrides["debug"] = args.debug
        elif hasattr(args, "verbose") and args.verbose:
            overrides["debug"] = args.verbose

        return overrides

    def _deep_merge(self, base: dict[str, Any], update: dict[str, Any]) -> None:
        """Deep merge update dictionary into base dictionary."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    @model_validator(mode="after")
    def validate_config(self) -> "Config":
        """Validate the configuration after initialization."""
        # Ensure database path is set
        if not self.database.path:
            # Try to detect project root from target_dir or auto-detect
            from chunkhound.utils.project_detection import find_project_root

            # Use the target_dir if it was provided during initialization
            start_path = getattr(self, "_target_dir", None)
            project_root = find_project_root(start_path)

            # Set default database path in project root
            self.database.path = project_root / ".chunkhound" / "db"

        # Ensure database path is absolute
        if self.database.path and not self.database.path.is_absolute():
            self.database.path = self.database.path.resolve()

        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump(exclude_none=True)

    def validate_for_command(self, command: str) -> list[str]:
        """
        Validate configuration for a specific command.

        Args:
            command: Command name ('index', 'mcp', etc.)

        Returns:
            List of validation errors (empty if valid)
        """
        # Import here to avoid circular imports
        from chunkhound.api.cli.utils.config_helpers import validate_config_for_command

        return validate_config_for_command(self, command)

    def get_missing_config(self) -> list[str]:
        """
        Get list of missing required configuration parameters.

        Returns:
            List of missing configuration parameter names
        """
        missing = []

        # Check embedding configuration if it exists
        if self.embedding:
            if hasattr(self.embedding, "get_missing_config"):
                embedding_missing = self.embedding.get_missing_config()
                for item in embedding_missing:
                    missing.append(f"embedding.{item}")
        # Note: If embedding is None, we don't assume a default provider
        # Commands like index and search can work without embeddings

        return missing

    def is_fully_configured(self) -> bool:
        """
        Check if all required configuration is present.

        Returns:
            True if fully configured, False otherwise
        """
        return self.embedding is not None and self.embedding.is_provider_configured()


# Global configuration instance
_global_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        # Create config with automatic project detection
        _global_config = Config()
    return _global_config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _global_config
    _global_config = None
