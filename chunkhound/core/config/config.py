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
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator, ConfigDict

from .database_config import DatabaseConfig
from .embedding_config import EmbeddingConfig
from .indexing_config import IndexingConfig
from .mcp_config import MCPConfig


class Config(BaseModel):
    """Centralized configuration for ChunkHound."""
    
    model_config = ConfigDict(validate_assignment=True)
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: Optional[EmbeddingConfig] = Field(default=None)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    debug: bool = Field(default=False)
    
    def __init__(
        self, 
        config_file: Optional[Path] = None, 
        overrides: Optional[Dict[str, Any]] = None,
        target_dir: Optional[Path] = None,
        **kwargs
    ):
        """Initialize configuration with hierarchical loading.
        
        Args:
            config_file: Optional path to configuration file (from --config)
            overrides: Optional dictionary of CLI overrides
            target_dir: Optional target directory to check for .chunkhound.json
            **kwargs: Additional keyword arguments
        """
        # Store target_dir for use in validation
        self._target_dir = target_dir
        
        # Start with defaults
        config_data = {}
        
        # 1. Load environment variables (highest precedence - preserve these)
        env_vars = self._load_env_vars()
        config_data.update(env_vars)
        
        # Make a deep copy of env vars to preserve them during merging
        import copy
        preserved_env_vars = copy.deepcopy(env_vars)
        
        # 2. Load config file if provided (from --config)
        if config_file and config_file.exists():
            import json
            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                    # Merge file config, but preserve env vars
                    self._deep_merge(config_data, file_config)
                    # Restore environment variables (they have higher precedence)
                    self._deep_merge(config_data, preserved_env_vars)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in config file {config_file}: {e}. "
                    "Please check the file format and try again."
                )
        
        # 3. Check for .chunkhound.json in target directory
        # Always use target_dir if provided, otherwise auto-detect project root
        if target_dir is None:
            from chunkhound.utils.project_detection import find_project_root
            target_dir = find_project_root()
        
        if target_dir and target_dir.exists():
            local_config_path = target_dir / ".chunkhound.json"
            if local_config_path.exists():
                import json
                try:
                    with open(local_config_path) as f:
                        local_config = json.load(f)
                        # Merge local config, but preserve env vars
                        self._deep_merge(config_data, local_config)
                        # Restore environment variables (they have higher precedence)
                        self._deep_merge(config_data, preserved_env_vars)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON in config file {local_config_path}: {e}. "
                        "Please check the file format and try again."
                    )
        
        # 4. Apply CLI overrides
        if overrides:
            self._deep_merge(config_data, overrides)
            
        # 5. Merge with any additional kwargs
        if kwargs:
            self._deep_merge(config_data, kwargs)
            
        # For EmbeddingConfig which is a BaseSettings, we need special handling
        if 'embedding' in config_data and isinstance(config_data['embedding'], dict):
            # Create EmbeddingConfig instance with the data, disabling env var loading
            config_data['embedding'] = EmbeddingConfig(_env_file=None, **config_data['embedding'])
        
        # Initialize the model
        super().__init__(**config_data)
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """Load configuration from environment variables.
        
        Supports both legacy and new environment variable names.
        Uses CHUNKHOUND_ prefix with __ delimiter for nested values.
        """
        config = {}
        
        # Debug mode
        if os.getenv("CHUNKHOUND_DEBUG"):
            config["debug"] = os.getenv("CHUNKHOUND_DEBUG", "").lower() in ("true", "1", "yes")
        
        # Database configuration
        # Support both old and new environment variable names
        if db_path := (os.getenv("CHUNKHOUND_DATABASE__PATH") or os.getenv("CHUNKHOUND_DB_PATH")):
            config.setdefault("database", {})["path"] = db_path
        if db_provider := os.getenv("CHUNKHOUND_DATABASE__PROVIDER"):
            config.setdefault("database", {})["provider"] = db_provider
        if index_type := os.getenv("CHUNKHOUND_DATABASE__LANCEDB_INDEX_TYPE"):
            config.setdefault("database", {})["lancedb_index_type"] = index_type
            
        # Embedding configuration
        embedding_config = {}
        
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
        if max_concurrent := os.getenv("CHUNKHOUND_EMBEDDING__MAX_CONCURRENT"):
            embedding_config["max_concurrent"] = int(max_concurrent)
            
        if embedding_config:
            config["embedding"] = embedding_config
            
        # MCP configuration
        mcp_config = {}
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
        indexing_config = {}
        if watch := os.getenv("CHUNKHOUND_INDEXING__WATCH"):
            indexing_config["watch"] = watch.lower() in ("true", "1", "yes")
        if debounce := os.getenv("CHUNKHOUND_INDEXING__DEBOUNCE_MS"):
            indexing_config["debounce_ms"] = int(debounce)
        if batch_size := os.getenv("CHUNKHOUND_INDEXING__BATCH_SIZE"):
            indexing_config["batch_size"] = int(batch_size)
        if db_batch_size := os.getenv("CHUNKHOUND_INDEXING__DB_BATCH_SIZE"):
            indexing_config["db_batch_size"] = int(db_batch_size)
        if max_concurrent := os.getenv("CHUNKHOUND_INDEXING__MAX_CONCURRENT"):
            indexing_config["max_concurrent"] = int(max_concurrent)
        if force_reindex := os.getenv("CHUNKHOUND_INDEXING__FORCE_REINDEX"):
            indexing_config["force_reindex"] = force_reindex.lower() in ("true", "1", "yes")
        if cleanup := os.getenv("CHUNKHOUND_INDEXING__CLEANUP"):
            indexing_config["cleanup"] = cleanup.lower() in ("true", "1", "yes")
        if ignore_gitignore := os.getenv("CHUNKHOUND_INDEXING__IGNORE_GITIGNORE"):
            indexing_config["ignore_gitignore"] = ignore_gitignore.lower() in ("true", "1", "yes")
            
        # Include/exclude patterns
        if include := os.getenv("CHUNKHOUND_INDEXING__INCLUDE"):
            indexing_config["include"] = include.split(",")
        if exclude := os.getenv("CHUNKHOUND_INDEXING__EXCLUDE"):
            indexing_config["exclude"] = exclude.split(",")
            
        if indexing_config:
            config["indexing"] = indexing_config
            
        return config
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
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
            start_path = getattr(self, '_target_dir', None)
            project_root = find_project_root(start_path)
            
            # Set default database path in project root
            self.database.path = project_root / ".chunkhound" / "db"
        
        # Ensure database path is absolute
        if self.database.path and not self.database.path.is_absolute():
            self.database.path = self.database.path.resolve()
                
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump(exclude_none=True)
    
    @classmethod
    def from_cli_args(
        cls, 
        args: Any,
        config_file: Optional[Path] = None,
        target_dir: Optional[Path] = None
    ) -> "Config":
        """Create configuration from CLI arguments.
        
        Args:
            args: Parsed command line arguments
            config_file: Optional config file path (from --config)
            target_dir: Optional target directory to check for .chunkhound.json
            
        Returns:
            Configured Config instance
        """
        # Convert args to overrides dict
        overrides = {}
        
        # Database arguments
        if hasattr(args, "db") and args.db:
            overrides.setdefault("database", {})["path"] = args.db
        if hasattr(args, "database_provider") and args.database_provider:
            overrides.setdefault("database", {})["provider"] = args.database_provider
        if hasattr(args, "database_lancedb_index_type") and args.database_lancedb_index_type:
            overrides.setdefault("database", {})["lancedb_index_type"] = args.database_lancedb_index_type
            
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
            overrides.setdefault("embedding", {})["batch_size"] = args.embedding_batch_size
        if hasattr(args, "embedding_max_concurrent") and args.embedding_max_concurrent:
            overrides.setdefault("embedding", {})["max_concurrent"] = args.embedding_max_concurrent
        # Note: --no-embeddings is handled at the application level, not in config
            
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
        if hasattr(args, "watch") and args.watch:
            overrides.setdefault("indexing", {})["watch"] = args.watch
        if hasattr(args, "debounce_ms") and args.debounce_ms:
            overrides.setdefault("indexing", {})["debounce_ms"] = args.debounce_ms
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
        if hasattr(args, "indexing_ignore_gitignore") and args.indexing_ignore_gitignore:
            overrides.setdefault("indexing", {})["ignore_gitignore"] = args.indexing_ignore_gitignore
            
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
            
        # Create config with overrides
        return cls(config_file=config_file, overrides=overrides, target_dir=target_dir)
    
    @classmethod
    def from_environment(cls, project_root: Optional[Path] = None) -> "Config":
        """
        Create configuration from environment variables only.
        
        Args:
            project_root: Optional project root (for target_dir)
            
        Returns:
            Config instance with environment-based configuration
        """
        # Use provided project_root or auto-detect
        if project_root is None:
            from chunkhound.utils.project_detection import find_project_root
            project_root = find_project_root()
        
        # Load configuration with target_dir for consistent local config detection
        return cls(target_dir=project_root)
    
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
            if hasattr(self.embedding, 'get_missing_config'):
                embedding_missing = self.embedding.get_missing_config()
                for item in embedding_missing:
                    missing.append(f"embedding.{item}")
        else:
            # If embedding is None, check what would be missing for default provider
            try:
                from .embedding_config import EmbeddingConfig
                default_embedding = EmbeddingConfig(provider="openai")
                embedding_missing = default_embedding.get_missing_config()
                for item in embedding_missing:
                    missing.append(f"embedding.{item}")
            except Exception:
                missing.append("embedding.provider")
        
        return missing
    
    def is_fully_configured(self) -> bool:
        """
        Check if all required configuration is present.
        
        Returns:
            True if fully configured, False otherwise
        """
        return self.embedding is not None and self.embedding.is_provider_configured()
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert configuration to dictionary format.
        
        Returns:
            Configuration as dictionary
        """
        return {
            "embedding": self.embedding.model_dump() if self.embedding else None,
            "mcp": self.mcp.model_dump(),
            "indexing": self.indexing.model_dump(),
            "database": self.database.model_dump(),
            "debug": self.debug
        }


# Global configuration instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        # Import here to avoid circular imports
        from chunkhound.utils.project_detection import find_project_root
        # Create config with project root to detect .chunkhound.json
        project_root = find_project_root()
        _global_config = Config(target_dir=project_root)
    return _global_config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _global_config
    _global_config = None