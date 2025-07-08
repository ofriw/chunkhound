"""Database configuration for ChunkHound.

This module provides database-specific configuration with support for
multiple database providers and storage backends.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DatabaseConfig(BaseModel):
    """Database configuration with support for multiple providers.
    
    Configuration can be provided via:
    - Environment variables (CHUNKHOUND_DATABASE_*)
    - Configuration files
    - CLI arguments
    - Default values
    """
    
    # Database location
    path: Optional[Path] = Field(
        default=None,
        description="Path to database directory"
    )
    
    # Provider selection
    provider: Literal["duckdb", "lancedb"] = Field(
        default="duckdb",
        description="Database provider to use"
    )
    
    # LanceDB specific configuration
    lancedb_index_type: Literal["IVF_PQ", "IVF_HNSW_SQ"] = Field(
        default="IVF_PQ",
        description="Index type for LanceDB (IVF_PQ for efficiency, IVF_HNSW_SQ for quality)"
    )
    
    # Connection pool settings
    pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Database connection pool size"
    )
    
    max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Maximum overflow connections above pool_size"
    )
    
    # Performance settings
    cache_size: int = Field(
        default=1000,
        ge=0,
        description="Query cache size (0 to disable)"
    )
    
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Database operation timeout in seconds"
    )
    
    @field_validator("path")
    def validate_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Convert string paths to Path objects."""
        if v is not None and not isinstance(v, Path):
            return Path(v)
        return v
    
    @field_validator("provider")
    def validate_provider(cls, v: str) -> str:
        """Validate database provider selection."""
        valid_providers = ["duckdb", "lancedb"]
        if v not in valid_providers:
            raise ValueError(f"Invalid provider: {v}. Must be one of {valid_providers}")
        return v
    
    def get_db_path(self) -> Path:
        """Get the full database file path based on provider."""
        if self.path is None:
            raise ValueError("Database path not configured")
            
        # Ensure directory exists
        self.path.mkdir(parents=True, exist_ok=True)
        
        if self.provider == "duckdb":
            return self.path / "chunks.db"
        elif self.provider == "lancedb":
            return self.path / "lancedb"
        else:
            raise ValueError(f"Unknown database provider: {self.provider}")
    
    def is_configured(self) -> bool:
        """Check if database is properly configured."""
        return self.path is not None
    
    def __repr__(self) -> str:
        """String representation of database configuration."""
        return (
            f"DatabaseConfig("
            f"provider={self.provider}, "
            f"path={self.path}, "
            f"pool_size={self.pool_size})"
        )