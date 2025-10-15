"""
LLM configuration for ChunkHound deep research.

This module provides a type-safe, validated configuration system for LLM
providers with support for multiple configuration sources (environment
variables, config files, CLI arguments).
"""

import argparse
import os
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """
    LLM configuration for ChunkHound deep research.

    Configuration Sources (in order of precedence):
    1. CLI arguments
    2. Environment variables (CHUNKHOUND_LLM_*)
    3. Config files
    4. Default values

    Environment Variables:
        CHUNKHOUND_LLM_API_KEY=sk-...
        CHUNKHOUND_LLM_UTILITY_MODEL=gpt-5-nano
        CHUNKHOUND_LLM_SYNTHESIS_MODEL=gpt-5
        CHUNKHOUND_LLM_BASE_URL=https://api.openai.com/v1
        CHUNKHOUND_LLM_PROVIDER=openai
    """

    model_config = SettingsConfigDict(
        env_prefix="CHUNKHOUND_LLM_",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",  # Ignore unknown fields for forward compatibility
    )

    # Provider Selection
    provider: Literal["openai", "anthropic", "ollama"] = Field(
        default="openai", description="LLM provider (openai, anthropic, ollama)"
    )

    # Model Configuration (dual-model architecture)
    utility_model: str = Field(
        default="",  # Will be set by get_default_models() if empty
        description="Model for utility operations (query expansion, follow-ups, classification)",
    )

    synthesis_model: str = Field(
        default="",  # Will be set by get_default_models() if empty
        description="Model for final synthesis (large context analysis)",
    )

    api_key: SecretStr | None = Field(
        default=None, description="API key for authentication (provider-specific)"
    )

    base_url: str | None = Field(
        default=None, description="Base URL for the LLM API"
    )

    # Internal settings
    timeout: int = Field(default=60, description="Internal timeout for LLM calls")
    max_retries: int = Field(default=3, description="Internal max retries")

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

    def get_provider_configs(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Get provider-specific configuration dictionaries for utility and synthesis models.

        Returns:
            Tuple of (utility_config, synthesis_config)
        """
        # Get default models if not specified
        utility_default, synthesis_default = self.get_default_models()

        base_config = {
            "provider": self.provider,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        # Add API key if available
        if self.api_key:
            base_config["api_key"] = self.api_key.get_secret_value()

        # Add base URL if available
        if self.base_url:
            base_config["base_url"] = self.base_url

        # Build utility config
        utility_config = base_config.copy()
        utility_config["model"] = self.utility_model or utility_default

        # Build synthesis config
        synthesis_config = base_config.copy()
        synthesis_config["model"] = self.synthesis_model or synthesis_default

        return utility_config, synthesis_config

    def get_default_models(self) -> tuple[str, str]:
        """
        Get default model names for utility and synthesis based on provider.

        Returns:
            Tuple of (utility_model, synthesis_model)
        """
        # Provider-specific smart defaults
        if self.provider == "openai":
            return ("gpt-5-nano", "gpt-5")
        elif self.provider == "anthropic":
            return ("claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022")
        elif self.provider == "ollama":
            # Ollama: use same model for both (local deployment)
            return ("llama3.2", "llama3.2")
        else:
            return ("gpt-5-nano", "gpt-5")

    def is_provider_configured(self) -> bool:
        """
        Check if the selected provider is properly configured.

        Returns:
            True if provider is properly configured
        """
        if self.provider == "ollama":
            # Ollama doesn't require API key
            return True
        else:
            # OpenAI and Anthropic require API key
            return self.api_key is not None

    def get_missing_config(self) -> list[str]:
        """
        Get list of missing required configuration.

        Returns:
            List of missing configuration parameter names
        """
        missing = []

        if self.provider != "ollama" and not self.api_key:
            missing.append("api_key (set CHUNKHOUND_LLM_API_KEY)")

        return missing

    @classmethod
    def add_cli_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add LLM-related CLI arguments."""
        parser.add_argument(
            "--llm-utility-model",
            help="Model for utility operations (query expansion, follow-ups, classification)",
        )

        parser.add_argument(
            "--llm-synthesis-model",
            help="Model for final synthesis (large context analysis)",
        )

        parser.add_argument(
            "--llm-api-key",
            help="API key for LLM provider (uses env var if not specified)",
        )

        parser.add_argument(
            "--llm-base-url",
            help="Base URL for LLM API (uses env var if not specified)",
        )

        parser.add_argument(
            "--llm-provider",
            choices=["openai", "anthropic", "ollama"],
            help="LLM provider (default: openai)",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load LLM config from environment variables."""
        config = {}

        if api_key := os.getenv("CHUNKHOUND_LLM_API_KEY"):
            config["api_key"] = api_key
        if base_url := os.getenv("CHUNKHOUND_LLM_BASE_URL"):
            config["base_url"] = base_url
        if provider := os.getenv("CHUNKHOUND_LLM_PROVIDER"):
            config["provider"] = provider
        if utility_model := os.getenv("CHUNKHOUND_LLM_UTILITY_MODEL"):
            config["utility_model"] = utility_model
        if synthesis_model := os.getenv("CHUNKHOUND_LLM_SYNTHESIS_MODEL"):
            config["synthesis_model"] = synthesis_model

        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract LLM config from CLI arguments."""
        overrides = {}

        if hasattr(args, "llm_utility_model") and args.llm_utility_model:
            overrides["utility_model"] = args.llm_utility_model
        if hasattr(args, "llm_synthesis_model") and args.llm_synthesis_model:
            overrides["synthesis_model"] = args.llm_synthesis_model
        if hasattr(args, "llm_api_key") and args.llm_api_key:
            overrides["api_key"] = args.llm_api_key
        if hasattr(args, "llm_base_url") and args.llm_base_url:
            overrides["base_url"] = args.llm_base_url
        if hasattr(args, "llm_provider") and args.llm_provider:
            overrides["provider"] = args.llm_provider

        return overrides

    def __repr__(self) -> str:
        """String representation hiding sensitive information."""
        api_key_display = "***" if self.api_key else None
        utility_model, synthesis_model = self.get_default_models()
        utility_display = self.utility_model or utility_model
        synthesis_display = self.synthesis_model or synthesis_model
        return (
            f"LLMConfig("
            f"provider={self.provider}, "
            f"utility_model={utility_display}, "
            f"synthesis_model={synthesis_display}, "
            f"api_key={api_key_display}, "
            f"base_url={self.base_url})"
        )
