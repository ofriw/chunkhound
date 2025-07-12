"""
Unified embedding configuration system for ChunkHound.

This module provides a type-safe, validated configuration system that supports
multiple embedding providers and configuration sources (environment variables,
config files, CLI arguments) with consistent behavior across MCP server and
indexing flows.
"""

from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingConfig(BaseSettings):
    """
    Unified configuration for embedding providers.

    This class provides consistent configuration management across all ChunkHound
    execution modes (MCP server and indexing flow) with support for multiple
    configuration sources and full type validation.

    Configuration Sources (in order of precedence):
    1. Runtime parameters (highest priority)
    2. Configuration files (when explicitly specified via --config)
    3. Environment variables (CHUNKHOUND_EMBEDDING_*)
    4. Default values (lowest priority)

    Environment Variable Examples:
        CHUNKHOUND_EMBEDDING_PROVIDER=openai
        CHUNKHOUND_EMBEDDING_API_KEY=sk-...
        CHUNKHOUND_EMBEDDING_MODEL=text-embedding-3-small
        CHUNKHOUND_EMBEDDING_BASE_URL=https://api.openai.com/v1
        CHUNKHOUND_EMBEDDING_BATCH_SIZE=100
        CHUNKHOUND_EMBEDDING_TIMEOUT=60
    """

    model_config = SettingsConfigDict(
        env_prefix="CHUNKHOUND_EMBEDDING_",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",  # Ignore unknown fields for forward compatibility
    )

    # Provider Selection
    provider: Literal["openai", "openai-compatible", "tei", "bge-in-icl"] = Field(
        description="Embedding provider to use (required)"
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

    # Performance Configuration
    batch_size: int = Field(
        default=50, ge=1, le=1000, description="Batch size for embedding generation"
    )

    timeout: int = Field(
        default=30, ge=1, le=300, description="Request timeout in seconds"
    )

    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum number of retry attempts"
    )

    max_concurrent_batches: int = Field(
        default=3, ge=1, le=20, description="Maximum concurrent embedding batches"
    )

    optimization_batch_frequency: int = Field(
        default=1000,
        ge=0,
        le=10000,
        description="Optimize database every N batches during embedding generation (0 to disable)",
    )

    # Provider-Specific Configuration
    dimensions: int | None = Field(
        default=None,
        ge=1,
        le=8192,
        description="Embedding dimensions (for openai-compatible provider)",
    )

    # BGE-IN-ICL Specific Configuration
    language: str = Field(
        default="auto", description="Programming language for BGE-IN-ICL context"
    )

    enable_icl: bool = Field(
        default=True, description="Enable in-context learning features for BGE-IN-ICL"
    )

    adaptive_batching: bool = Field(
        default=True, description="Enable adaptive batch sizing for BGE-IN-ICL"
    )

    min_batch_size: int = Field(
        default=10, ge=1, le=100, description="Minimum batch size for adaptive batching"
    )

    max_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum batch size for adaptive batching",
    )

    context_cache_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Size of context cache for BGE-IN-ICL optimization",
    )

    @model_validator(mode="after")
    def validate_provider_is_set(self) -> "EmbeddingConfig":
        """Ensure provider is explicitly set."""
        if not hasattr(self, "provider") or self.provider is None:
            raise ValueError(
                "Embedding provider must be explicitly selected. Available options: "
                "openai, openai-compatible, tei, bge-in-icl. "
                "Set via --provider, CHUNKHOUND_EMBEDDING__PROVIDER, or in config file."
            )
        return self
    
    @field_validator("model")
    def validate_model(cls, v: str | None, info) -> str | None:
        """Validate model name based on provider."""
        if v is None:
            return v

        provider = info.data.get("provider", "openai") if info.data else "openai"

        # Provider-specific model validation
        if provider == "openai":
            valid_models = [
                "text-embedding-3-small",
                "text-embedding-3-large",
                "text-embedding-ada-002",
            ]
            if v and v not in valid_models:
                # Allow custom models but warn about common typos
                common_typos = {
                    "text-embedding-3-small": "text-embedding-3-small",
                    "text-embedding-small": "text-embedding-3-small",
                    "text-embedding-large": "text-embedding-3-large",
                }
                if v in common_typos:
                    return common_typos[v]

        return v

    @field_validator("base_url")
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate and normalize base URL."""
        if v is None:
            return v

        # Remove trailing slash for consistency
        v = v.rstrip("/")

        # Basic URL validation
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")

        return v

    @field_validator("batch_size")
    def validate_batch_size_for_provider(cls, v: int, info) -> int:
        """Validate batch size based on provider capabilities."""
        provider = info.data.get("provider", "openai") if info.data else "openai"

        # Provider-specific batch size limits
        limits = {
            "openai": (1, 2048),
            "openai-compatible": (1, 1000),
            "tei": (1, 512),
            "bge-in-icl": (1, 256),
        }

        min_size, max_size = limits.get(provider, (1, 1000))

        if v < min_size or v > max_size:
            raise ValueError(
                f"batch_size for {provider} must be between {min_size} and {max_size}"
            )

        return v

    def get_provider_config(self) -> dict[str, Any]:
        """
        Get provider-specific configuration dictionary.

        Returns:
            Dictionary containing configuration parameters for the selected provider
        """
        base_config = {
            "provider": self.provider,
            "model": self.get_default_model(),  # Always provide resolved model to factory
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

        # Provider-specific configuration
        if self.provider == "openai-compatible":
            if self.dimensions:
                base_config["dimensions"] = self.dimensions

        elif self.provider == "bge-in-icl":
            base_config.update(
                {
                    "language": self.language,
                    "enable_icl": self.enable_icl,
                    "adaptive_batching": self.adaptive_batching,
                    "min_batch_size": self.min_batch_size,
                    "max_batch_size": self.max_batch_size,
                    "context_cache_size": self.context_cache_size,
                }
            )

        return base_config

    def get_default_model(self) -> str:
        """
        Get the default model for the selected provider.

        Returns:
            Default model name for the provider
        
        Raises:
            ValueError: If no provider is selected
        """
        if not self.provider:
            raise ValueError("No embedding provider selected. Please specify a provider.")
            
        defaults = {
            "openai": "text-embedding-3-small",
            "openai-compatible": "text-embedding-ada-002",
            "tei": "sentence-transformers/all-MiniLM-L6-v2",
            "bge-in-icl": "bge-in-icl",
        }

        return self.model or defaults.get(self.provider, "text-embedding-3-small")

    def is_provider_configured(self) -> bool:
        """
        Check if the provider is properly configured.

        Returns:
            True if the provider has all required configuration
        """
        # OpenAI requires API key
        if self.provider == "openai":
            return self.api_key is not None

        # OpenAI-compatible requires base URL
        elif self.provider == "openai-compatible":
            return self.base_url is not None

        # TEI requires base URL
        elif self.provider == "tei":
            return self.base_url is not None

        # BGE-IN-ICL requires base URL
        elif self.provider == "bge-in-icl":
            return self.base_url is not None

        return False

    def get_missing_config(self) -> list[str]:
        """
        Get list of missing required configuration parameters.

        Returns:
            List of missing configuration parameter names
        """
        missing = []
        
        # Check if provider is set first
        if not self.provider:
            missing.append("provider (--provider, CHUNKHOUND_EMBEDDING__PROVIDER, or in config file)")
            return missing  # Return early as other checks depend on provider

        if self.provider == "openai" and not self.api_key:
            missing.append("api_key (CHUNKHOUND_EMBEDDING_API_KEY)")

        elif (
            self.provider in ["openai-compatible", "tei", "bge-in-icl"]
            and not self.base_url
        ):
            missing.append("base_url (CHUNKHOUND_EMBEDDING_BASE_URL)")

        return missing

    def __repr__(self) -> str:
        """String representation hiding sensitive information."""
        api_key_display = "***" if self.api_key else None
        return (
            f"EmbeddingConfig("
            f"provider={self.provider}, "
            f"model={self.get_default_model()}, "
            f"api_key={api_key_display}, "
            f"base_url={self.base_url}, "
            f"batch_size={self.batch_size})"
        )
