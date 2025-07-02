"""
Unified configuration system for ChunkHound.

This module provides a single, type-safe configuration model that unifies
all ChunkHound configuration across embedding, MCP, indexing, and database
components with hierarchical loading from multiple sources.
"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import the proper EmbeddingConfig class with validation methods
from .embedding_config import EmbeddingConfig


def _get_default_include_patterns() -> list[str]:
    """Get complete default patterns from Language enum.
    
    Returns all supported file extensions as glob patterns.
    This is the single source of truth for default file discovery.
    """
    from core.types.common import Language
    patterns = []
    for ext in Language.get_all_extensions():
        patterns.append(f"**/*{ext}")
    # Add special filename patterns
    patterns.extend(["**/Makefile", "**/makefile", "**/GNUmakefile", "**/gnumakefile"])
    return patterns


class MCPConfig(BaseModel):
    """MCP server configuration."""
    
    transport: Literal['stdio', 'http'] = Field(
        default='stdio',
        description="Transport type for MCP server"
    )
    
    port: int = Field(
        default=3000,
        ge=1,
        le=65535,
        description="Port for HTTP transport"
    )
    
    host: str = Field(
        default='localhost',
        description="Host for HTTP transport"
    )
    
    cors: bool = Field(
        default=False,
        description="Enable CORS for HTTP transport"
    )


class IndexingConfig(BaseModel):
    """Indexing configuration."""
    
    include_patterns: list[str] = Field(
        default_factory=_get_default_include_patterns,
        description="File patterns to include in indexing (all supported languages)"
    )
    
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            # Virtual environments and package managers
            '**/node_modules/**', '**/.git/**', '**/__pycache__/**', '**/venv/**', '**/.venv/**', '**/.mypy_cache/**',
            # Build artifacts and distributions  
            '**/dist/**', '**/build/**', '**/target/**', '**/.pytest_cache/**',
            # IDE and editor files
            '**/.vscode/**', '**/.idea/**', '**/.vs/**',
            # Cache and temporary directories
            '**/.cache/**', '**/tmp/**', '**/temp/**',
            # Backup and old files
            '**/*.backup', '**/*.bak', '**/*~', '**/*.old',
            # Large generated files
            '**/*.min.js', '**/*.min.css', '**/bundle.js', '**/vendor.js'
        ],
        description="File patterns to exclude from indexing"
    )
    
    def get_effective_exclude_patterns(self, base_dir: Path | None = None) -> list[str]:
        """Get effective exclude patterns including .gitignore files.
        
        Args:
            base_dir: Base directory to search for .gitignore files
            
        Returns:
            Combined exclude patterns from config and .gitignore files
        """
        patterns = self.exclude_patterns.copy()
        
        if base_dir is None:
            base_dir = Path.cwd()
            
        # Parse .gitignore file if it exists
        gitignore_path = base_dir / '.gitignore'
        if gitignore_path.exists():
            try:
                gitignore_patterns = self._parse_gitignore(gitignore_path)
                patterns.extend(gitignore_patterns)
            except Exception:
                # Silently ignore gitignore parsing errors
                pass
                
        return patterns
    
    def _parse_gitignore(self, gitignore_path: Path) -> list[str]:
        """Parse .gitignore file into exclude patterns.
        
        Args:
            gitignore_path: Path to .gitignore file
            
        Returns:
            List of exclude patterns
        """
        patterns = []
        
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                        
                    # Handle negation patterns (not supported, skip)
                    if line.startswith('!'):
                        continue
                    
                    # Convert gitignore patterns to glob patterns
                    if line.endswith('/'):
                        # Directory pattern
                        patterns.append(f"**/{line}**")
                        patterns.append(f"**/{line[:-1]}/**")
                    elif '/' in line:
                        # Path pattern
                        if line.startswith('/'):
                            line = line[1:]  # Remove leading slash
                        patterns.append(f"**/{line}")
                        if not line.endswith('*'):
                            patterns.append(f"**/{line}/**")
                    else:
                        # Filename pattern
                        patterns.append(f"**/{line}")
                        patterns.append(f"**/{line}/**")
                        
        except Exception:
            # Return empty list on any parsing error
            pass
            
        return patterns
    
    watch: bool = Field(
        default=False,
        description="Enable file watching for automatic updates"
    )
    
    debounce_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="File change debounce time in milliseconds"
    )
    
    batch_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Batch size for processing files"
    )
    
    db_batch_size: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Number of records per database transaction"
    )
    
    max_concurrent: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Maximum concurrent file processing"
    )
    
    force_reindex: bool = Field(
        default=False,
        description="Force reindexing of all files"
    )
    
    cleanup: bool = Field(
        default=False,
        description="Clean up orphaned chunks from deleted files"
    )


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    path: str = Field(
        default='.chunkhound.db',
        description="Path to database file"
    )
    provider: Literal['duckdb', 'lancedb'] = Field(
        default='duckdb',
        description="Database provider (duckdb or lancedb)"
    )
    lancedb_index_type: Literal['ivf_pq', 'ivf_hnsw_sq'] | None = Field(
        default=None,
        description="LanceDB index type (auto-configured if not specified)"
    )


class ChunkHoundConfig(BaseSettings):
    """
    Unified configuration for ChunkHound.
    This class provides consistent configuration management across all ChunkHound
    components with support for hierarchical loading from multiple sources.
    
    Configuration Sources (in order of precedence):
    1. Runtime parameters (highest priority)
    2. Environment variables (CHUNKHOUND_*)
    3. Project config file (.chunkhound.json)
    4. User config file (~/.chunkhound/config.json)
    5. Default values (lowest priority)
    
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
        env_prefix='CHUNKHOUND_',
        env_nested_delimiter='__',
        case_sensitive=False,
        validate_default=True,
        extra='ignore',
        # Custom sources for hierarchical loading
        env_file=None,  # Disable automatic .env loading
    )
    
    # Component configurations
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding provider configuration"
    )
    
    mcp: MCPConfig = Field(
        default_factory=MCPConfig,
        description="MCP server configuration"
    )
    
    indexing: IndexingConfig = Field(
        default_factory=IndexingConfig,
        description="Indexing configuration"
    )
    
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration"
    )
    
    # Global settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    @classmethod
    def load_hierarchical(cls, 
                         project_dir: Path | None = None,
                         **override_values: Any) -> 'ChunkHoundConfig':
        """
        Load configuration from hierarchical sources.
        
        Args:
            project_dir: Project directory to search for .chunkhound.json
            **override_values: Runtime parameter overrides
            
        Returns:
            Loaded and validated configuration
        """
        config_data = {}
        
        # 1. Load user config file (~/.chunkhound/config.json)
        user_config_path = Path.home() / '.chunkhound' / 'config.json'
        if user_config_path.exists():
            try:
                with open(user_config_path) as f:
                    user_config = json.load(f)
                config_data.update(user_config)
            except (json.JSONDecodeError, OSError) as e:
                if os.getenv('CHUNKHOUND_DEBUG'):
                    print(f"Warning: Failed to load user config {user_config_path}: {e}")
        
        # 2. Load project config file (.chunkhound.json)
        if project_dir is None:
            project_dir = Path.cwd()
        
        project_config_path = project_dir / '.chunkhound.json'
        if project_config_path.exists():
            try:
                with open(project_config_path) as f:
                    project_config = json.load(f)
                config_data.update(project_config)
            except (json.JSONDecodeError, OSError) as e:
                if os.getenv('CHUNKHOUND_DEBUG'):
                    print(f"Warning: Failed to load project config {project_config_path}: {e}")
        
        # 3. Apply runtime overrides
        config_data.update(override_values)
        
        # 4. Create instance with environment variable support
        # Handle embedding config specially to ensure proper EmbeddingConfig instantiation
        if 'embedding' in config_data and isinstance(config_data['embedding'], dict):
            config_data['embedding'] = EmbeddingConfig(**config_data['embedding'])
        
        return cls(**config_data)
    
    @field_validator('embedding')
    def validate_embedding_config(cls, v: EmbeddingConfig) -> EmbeddingConfig:
        """Validate embedding configuration for provider requirements."""
        # Check for legacy environment variables and warn
        if not v.api_key and os.getenv('OPENAI_API_KEY'):
            if os.getenv('CHUNKHOUND_DEBUG'):
                print("Warning: Using legacy OPENAI_API_KEY. Consider setting CHUNKHOUND_EMBEDDING__API_KEY")
            # Create new config with legacy API key
            config_dict = v.model_dump()
            config_dict['api_key'] = os.getenv('OPENAI_API_KEY')
            v = EmbeddingConfig(**config_dict)
        
        if not v.base_url and os.getenv('OPENAI_BASE_URL'):
            if os.getenv('CHUNKHOUND_DEBUG'):
                print("Warning: Using legacy OPENAI_BASE_URL. Consider setting CHUNKHOUND_EMBEDDING__BASE_URL")
            # Create new config with legacy base URL
            config_dict = v.model_dump()
            config_dict['base_url'] = os.getenv('OPENAI_BASE_URL')
            v = EmbeddingConfig(**config_dict)
        
        return v
    
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
            missing.append(f'embedding.{item}')
        
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
        return self.model_dump(mode='json', exclude_none=True)
    
    def save_to_file(self, file_path: Path) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            file_path: Path to save configuration file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        config_dict = self.to_dict()
        
        # Remove sensitive data from saved config
        if 'embedding' in config_dict and 'api_key' in config_dict['embedding']:
            del config_dict['embedding']['api_key']
        
        with open(file_path, 'w') as f:
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

    @classmethod
    def get_default_exclude_patterns(cls) -> list[str]:
        """Get the default exclude patterns for file indexing.
        
        Returns:
            List of default exclude patterns
        """
        # Create a temporary instance to get the default patterns
        temp_config = IndexingConfig()
        return temp_config.exclude_patterns


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
        _config_instance = ChunkHoundConfig.load_hierarchical()
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