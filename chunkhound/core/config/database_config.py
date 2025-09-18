"""Database configuration for ChunkHound.

This module provides database-specific configuration with support for
multiple database providers and storage backends.
"""

import argparse
import os
from pathlib import Path
from typing import Any, Literal

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
    path: Path | None = Field(default=None, description="Path to database directory")

    # Provider selection
    provider: Literal["duckdb", "lancedb"] = Field(
        default="duckdb", description="Database provider to use"
    )

    @field_validator("path")
    def validate_path(cls, v: Path | None) -> Path | None:
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

    @classmethod
    def add_cli_arguments(
        cls, parser: argparse.ArgumentParser, required_path: bool = False
    ) -> None:
        """Add database-related CLI arguments."""
        parser.add_argument(
            "--db",
            "--database-path",
            type=Path,
            help="Database file path (default: from config file or .chunkhound.db)",
            required=required_path,
        )

        parser.add_argument(
            "--database-provider",
            choices=["duckdb", "lancedb"],
            help="Database provider to use",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load database config from environment variables."""
        config = {}
        # Support both new and legacy env var names
        if db_path := (
            os.getenv("CHUNKHOUND_DATABASE__PATH") or os.getenv("CHUNKHOUND_DB_PATH")
        ):
            config["path"] = Path(db_path)
        if provider := os.getenv("CHUNKHOUND_DATABASE__PROVIDER"):
            config["provider"] = provider
        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract database config from CLI arguments."""
        overrides = {}
        if hasattr(args, "db") and args.db:
            overrides["path"] = args.db
        if hasattr(args, "database_path") and args.database_path:
            overrides["path"] = args.database_path
        if hasattr(args, "database_provider") and args.database_provider:
            overrides["provider"] = args.database_provider
        return overrides

    def __repr__(self) -> str:
        """String representation of database configuration."""
        return f"DatabaseConfig(provider={self.provider}, path={self.path})"
