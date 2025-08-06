"""Indexing configuration for ChunkHound.

This module provides configuration for the file indexing process including
batch processing, and pattern matching.
"""

import argparse
import os
from typing import Any

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

    Controls how files are discovered and indexed.
    """

    # Batch processing
    batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of files to process in a single batch",
    )

    db_batch_size: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Number of chunks to insert in a single database batch",
    )

    max_concurrent: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent file processing tasks"
    )

    # Indexing behavior
    force_reindex: bool = Field(
        default=False, description="Force re-indexing of all files"
    )

    cleanup: bool = Field(
        default=True, description="Remove chunks from deleted files during indexing"
    )

    ignore_gitignore: bool = Field(
        default=False, description="Ignore .gitignore patterns when discovering files"
    )

    # File patterns
    include: list[str] = Field(
        default_factory=lambda: _get_default_include_patterns(),
        description="Glob patterns for files to include (all supported languages)",
    )

    exclude: list[str] = Field(
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
            # Editor temporary file patterns
            # Vim patterns
            "**/*.swp",
            "**/*.swo",
            "**/.*.swp",
            "**/.*.swo",
            # VS Code / general patterns
            "**/*.tmp.*",
            "**/*.*.tmp",
            "**/*~.tmp",
            # Emacs patterns
            "**/.*#",
            "**/#*#",
            "**/.*~",
            # Generic temp patterns
            "**/*.tmp???",
            "**/*.???tmp",
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
        description="Glob patterns for files to exclude",
    )

    # Performance tuning
    max_file_size_mb: int = Field(
        default=10, ge=1, le=100, description="Maximum file size in MB to index"
    )

    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Number of characters to overlap between chunks",
    )

    min_chunk_size: int = Field(
        default=50, ge=10, le=1000, description="Minimum chunk size in characters"
    )

    max_chunk_size: int = Field(
        default=2000, ge=100, le=10000, description="Maximum chunk size in characters"
    )

    @field_validator("include", "exclude")
    def validate_patterns(cls, v: list[str]) -> list[str]:
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

    @classmethod
    def add_cli_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add indexing-related CLI arguments."""
        parser.add_argument(
            "--indexing-batch-size",
            type=int,
            help="Number of files to process per batch",
        )

        parser.add_argument(
            "--db-batch-size",
            type=int,
            help="Number of records per database transaction",
        )

        parser.add_argument(
            "--indexing-max-concurrent",
            type=int,
            help="Maximum concurrent file processing tasks",
        )

        parser.add_argument(
            "--force-reindex",
            action="store_true",
            help="Force reindexing of all files, even if they haven't changed",
        )

        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up orphaned chunks from deleted files",
        )

        parser.add_argument(
            "--indexing-ignore-gitignore",
            action="store_true",
            help="Ignore .gitignore files when scanning",
        )

        parser.add_argument(
            "--include",
            action="append",
            help="File patterns to include (can be specified multiple times)",
        )

        parser.add_argument(
            "--exclude",
            action="append",
            help="File patterns to exclude (can be specified multiple times)",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load indexing config from environment variables."""
        config = {}

        if batch_size := os.getenv("CHUNKHOUND_INDEXING__BATCH_SIZE"):
            config["batch_size"] = int(batch_size)
        if db_batch_size := os.getenv("CHUNKHOUND_INDEXING__DB_BATCH_SIZE"):
            config["db_batch_size"] = int(db_batch_size)
        if max_concurrent := os.getenv("CHUNKHOUND_INDEXING__MAX_CONCURRENT"):
            config["max_concurrent"] = int(max_concurrent)
        if force_reindex := os.getenv("CHUNKHOUND_INDEXING__FORCE_REINDEX"):
            config["force_reindex"] = force_reindex.lower() in ("true", "1", "yes")
        if cleanup := os.getenv("CHUNKHOUND_INDEXING__CLEANUP"):
            config["cleanup"] = cleanup.lower() in ("true", "1", "yes")
        if ignore_gitignore := os.getenv("CHUNKHOUND_INDEXING__IGNORE_GITIGNORE"):
            config["ignore_gitignore"] = ignore_gitignore.lower() in (
                "true",
                "1",
                "yes",
            )

        # Handle comma-separated include/exclude patterns
        if include := os.getenv("CHUNKHOUND_INDEXING__INCLUDE"):
            config["include"] = include.split(",")
        if exclude := os.getenv("CHUNKHOUND_INDEXING__EXCLUDE"):
            config["exclude"] = exclude.split(",")

        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract indexing config from CLI arguments."""
        overrides = {}

        if hasattr(args, "indexing_batch_size") and args.indexing_batch_size:
            overrides["batch_size"] = args.indexing_batch_size
        if hasattr(args, "db_batch_size") and args.db_batch_size:
            overrides["db_batch_size"] = args.db_batch_size
        if hasattr(args, "indexing_max_concurrent") and args.indexing_max_concurrent:
            overrides["max_concurrent"] = args.indexing_max_concurrent
        if hasattr(args, "force_reindex") and args.force_reindex:
            overrides["force_reindex"] = args.force_reindex
        if hasattr(args, "cleanup") and args.cleanup:
            overrides["cleanup"] = args.cleanup
        if (
            hasattr(args, "indexing_ignore_gitignore")
            and args.indexing_ignore_gitignore
        ):
            overrides["ignore_gitignore"] = args.indexing_ignore_gitignore

        # Include/exclude patterns
        if hasattr(args, "include") and args.include:
            overrides["include"] = args.include
        if hasattr(args, "exclude") and args.exclude:
            overrides["exclude"] = args.exclude

        return overrides

    def __repr__(self) -> str:
        """String representation of indexing configuration."""
        return (
            f"IndexingConfig("
            f"batch_size={self.batch_size}, "
            f"max_concurrent={self.max_concurrent}, "
            f"patterns={len(self.include)} includes, {len(self.exclude)} excludes)"
        )
