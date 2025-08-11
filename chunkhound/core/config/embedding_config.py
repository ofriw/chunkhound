"""
OpenAI embedding configuration for ChunkHound.

This module provides a type-safe, validated configuration system for OpenAI
embeddings with support for multiple configuration sources (environment
variables, config files, CLI arguments) across MCP server and indexing flows.
"""

import argparse
import os
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingConfig(BaseSettings):
    """
    OpenAI embedding configuration for ChunkHound.

    Configuration Sources (in order of precedence):
    1. CLI arguments
    2. Environment variables (CHUNKHOUND_EMBEDDING_*)
    3. Config files
    4. Default values

    Environment Variables:
        CHUNKHOUND_EMBEDDING_API_KEY=sk-...
        CHUNKHOUND_EMBEDDING_MODEL=text-embedding-3-small
        CHUNKHOUND_EMBEDDING_BASE_URL=https://api.openai.com/v1
    """

    model_config = SettingsConfigDict(
        env_prefix="CHUNKHOUND_EMBEDDING_",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",  # Ignore unknown fields for forward compatibility
    )

    # Provider Selection
    provider: Literal["openai"] = Field(
        default="openai",
        description="Embedding provider (openai)"
    )

    # Common Configuration
    model: str | None = Field(
        default=None,
        description="Embedding model name (uses provider default if not specified)",
    )

    api_key: SecretStr | None = Field(
        default=None, description="API key for authentication (provider-specific)"
    )

    base_url: str | None = Field(
        default=None, description="Base URL for the embedding API"
    )

    # Internal settings - not exposed to users
    batch_size: int = Field(default=100, description="Internal batch size")
    timeout: int = Field(default=30, description="Internal timeout")
    max_retries: int = Field(default=3, description="Internal max retries")
    max_concurrent_batches: int = Field(default=3, description="Internal concurrency")
    optimization_batch_frequency: int = Field(
        default=1000, description="Internal optimization frequency"
    )




    @field_validator("model")
    def validate_model(cls, v: str | None) -> str | None:  # noqa: N805
        """Fix common model name typos."""
        if v is None:
            return v

        # Fix common typos
        typo_fixes = {
            "text-embedding-small": "text-embedding-3-small",
            "text-embedding-large": "text-embedding-3-large",
        }

        return typo_fixes.get(v, v)

    @field_validator("base_url")
    def validate_base_url(cls, v: str | None) -> str | None:  # noqa: N805
        """Validate and normalize base URL."""
        if v is None:
            return v

        # Remove trailing slash for consistency
        v = v.rstrip("/")

        # Basic URL validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")

        return v


    def get_provider_config(self) -> dict[str, Any]:
        """
        Get provider-specific configuration dictionary.

        Returns:
            Dictionary containing configuration parameters for the selected provider
        """
        base_config = {
            "provider": self.provider,
            # Always provide resolved model to factory
            "model": self.get_default_model(),
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        # Add API key if available
        if self.api_key:
            base_config["api_key"] = self.api_key.get_secret_value()

        # Add base URL if available
        if self.base_url:
            base_config["base_url"] = self.base_url

        return base_config

    def get_default_model(self) -> str:
        """
        Get the model name, using default if not specified.

        Returns:
            Model name or default OpenAI model
        """
        return self.model or "text-embedding-3-small"

    def is_provider_configured(self) -> bool:
        """
        Check if OpenAI is properly configured.

        Returns:
            True if API key is available
        """
        return self.api_key is not None

    def get_missing_config(self) -> list[str]:
        """
        Get list of missing required configuration.

        Returns:
            List of missing configuration parameter names
        """
        if not self.api_key:
            return ["api_key (set CHUNKHOUND_EMBEDDING_API_KEY)"]
        return []

    @classmethod
    def add_cli_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add embedding-related CLI arguments."""
        parser.add_argument(
            "--model",
            "--embedding-model",
            help="Embedding model (default: text-embedding-3-small)",
        )

        parser.add_argument(
            "--api-key",
            "--embedding-api-key",
            help="API key for embedding provider (uses env var if not specified)",
        )

        parser.add_argument(
            "--base-url",
            "--embedding-base-url",
            help="Base URL for embedding API (uses env var if not specified)",
        )

        parser.add_argument(
            "--no-embeddings",
            action="store_true",
            help="Skip embedding generation (index code only)",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load embedding config from environment variables."""
        config = {}

        if api_key := os.getenv("CHUNKHOUND_EMBEDDING__API_KEY"):
            config["api_key"] = api_key
        if base_url := os.getenv("CHUNKHOUND_EMBEDDING__BASE_URL"):
            config["base_url"] = base_url
        if provider := os.getenv("CHUNKHOUND_EMBEDDING__PROVIDER"):
            config["provider"] = provider
        if model := os.getenv("CHUNKHOUND_EMBEDDING__MODEL"):
            config["model"] = model

        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract embedding config from CLI arguments."""
        overrides = {}

        # Handle model arguments (both variations)
        if hasattr(args, "model") and args.model:
            overrides["model"] = args.model
        if hasattr(args, "embedding_model") and args.embedding_model:
            overrides["model"] = args.embedding_model

        # Handle API key arguments (both variations)
        if hasattr(args, "api_key") and args.api_key:
            overrides["api_key"] = args.api_key
        if hasattr(args, "embedding_api_key") and args.embedding_api_key:
            overrides["api_key"] = args.embedding_api_key

        # Handle base URL arguments (both variations)
        if hasattr(args, "base_url") and args.base_url:
            overrides["base_url"] = args.base_url
        if hasattr(args, "embedding_base_url") and args.embedding_base_url:
            overrides["base_url"] = args.embedding_base_url


        # Handle no-embeddings flag (special case - disables embeddings)
        if hasattr(args, "no_embeddings") and args.no_embeddings:
            return {"disabled": True}  # This will be handled specially in main Config

        return overrides

    def __repr__(self) -> str:
        """String representation hiding sensitive information."""
        api_key_display = "***" if self.api_key else None
        return (
            f"EmbeddingConfig("
            f"provider={self.provider}, "
            f"model={self.get_default_model()}, "
            f"api_key={api_key_display}, "
            f"base_url={self.base_url})"
        )
