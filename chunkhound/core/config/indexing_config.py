"""Indexing configuration for ChunkHound.

This module provides configuration for the file indexing process including
file watching, batch processing, and pattern matching.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def _get_default_include_patterns() -> list[str]:
    """Get complete default patterns from Language enum.

    Returns all supported file extensions as glob patterns.
    This is the single source of truth for default file discovery.
    """
    from chunkhound.core.types.common import Language

    patterns = []
    for ext in Language.get_all_extensions():
        patterns.append(f"**/*{ext}")
    # Add special filename patterns
    patterns.extend(["**/Makefile", "**/makefile", "**/GNUmakefile", "**/gnumakefile"])
    return patterns


class IndexingConfig(BaseModel):
    """Configuration for file indexing behavior.
    
    Controls how files are discovered, indexed, and monitored for changes.
    """
    
    # File watching
    watch: bool = Field(
        default=False,
        description="Enable file watching for automatic re-indexing"
    )
    
    debounce_ms: int = Field(
        default=300,
        ge=0,
        le=10000,
        description="Debounce time in milliseconds for file changes"
    )
    
    # Batch processing
    batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of files to process in a single batch"
    )
    
    db_batch_size: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Number of chunks to insert in a single database batch"
    )
    
    max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent file processing tasks"
    )
    
    # Indexing behavior
    force_reindex: bool = Field(
        default=False,
        description="Force re-indexing of all files"
    )
    
    cleanup: bool = Field(
        default=True,
        description="Remove chunks from deleted files during indexing"
    )
    
    ignore_gitignore: bool = Field(
        default=False,
        description="Ignore .gitignore patterns when discovering files"
    )
    
    # File patterns
    include: List[str] = Field(
        default_factory=lambda: _get_default_include_patterns(),
        description="Glob patterns for files to include (all supported languages)"
    )
    
    exclude: List[str] = Field(
        default_factory=lambda: [
            # Virtual environments and package managers
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.mypy_cache/**",
            # Build artifacts and distributions
            "**/dist/**",
            "**/build/**",
            "**/target/**",
            "**/.pytest_cache/**",
            # IDE and editor files
            "**/.vscode/**",
            "**/.idea/**",
            "**/.vs/**",
            # Cache and temporary directories
            "**/.cache/**",
            "**/tmp/**",
            "**/temp/**",
            # Backup and old files
            "**/*.backup",
            "**/*.bak",
            "**/*~",
            "**/*.old",
            # Large generated files
            "**/*.min.js",
            "**/*.min.css",
            "**/bundle.js",
            "**/vendor.js",
        ],
        description="Glob patterns for files to exclude"
    )
    
    # Performance tuning
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file size in MB to index"
    )
    
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Number of characters to overlap between chunks"
    )
    
    min_chunk_size: int = Field(
        default=50,
        ge=10,
        le=1000,
        description="Minimum chunk size in characters"
    )
    
    max_chunk_size: int = Field(
        default=2000,
        ge=100,
        le=10000,
        description="Maximum chunk size in characters"
    )
    
    @field_validator("include", "exclude")
    def validate_patterns(cls, v: List[str]) -> List[str]:
        """Validate glob patterns."""
        if not isinstance(v, list):
            raise ValueError("Patterns must be a list")
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for pattern in v:
            if pattern not in seen:
                seen.add(pattern)
                unique.append(pattern)
        
        return unique
    
    @field_validator("debounce_ms")
    def validate_debounce(cls, v: int, info) -> int:
        """Validate debounce time when watching is enabled."""
        watch = info.data.get("watch", False) if info.data else False
        
        if watch and v < 100:
            # Increase debounce time for file watching to avoid excessive re-indexing
            return 100
        
        return v
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    def should_index_file(self, file_path: str) -> bool:
        """Check if a file should be indexed based on patterns.
        
        Note: This is a simplified check. The actual implementation
        should use proper glob matching.
        """
        # This is a placeholder - actual implementation would use
        # pathlib and fnmatch for proper pattern matching
        return True
    
    def __repr__(self) -> str:
        """String representation of indexing configuration."""
        return (
            f"IndexingConfig("
            f"watch={self.watch}, "
            f"batch_size={self.batch_size}, "
            f"max_concurrent={self.max_concurrent}, "
            f"patterns={len(self.include)} includes, {len(self.exclude)} excludes)"
        )