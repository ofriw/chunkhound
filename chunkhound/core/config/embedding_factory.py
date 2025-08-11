"""
Unified embedding provider factory for ChunkHound.

This module provides a factory pattern for creating embedding providers
with consistent configuration across all ChunkHound execution modes.
The factory supports all four embedding providers with unified configuration.
"""

from typing import TYPE_CHECKING, Any

from loguru import logger

from .embedding_config import EmbeddingConfig

if TYPE_CHECKING:
    from chunkhound.embeddings import (
        EmbeddingProvider,
        OpenAIEmbeddingProvider,
    )


class EmbeddingProviderFactory:
    """
    Factory for creating embedding providers from unified configuration.

    This factory provides consistent provider creation across MCP server
    and indexing flows, supporting all four embedding providers with
    type-safe configuration validation.
    """

    @staticmethod
    def create_provider(config: EmbeddingConfig) -> "EmbeddingProvider":
        """
        Create an embedding provider from configuration.

        Args:
            config: Validated embedding configuration

        Returns:
            Configured embedding provider instance

        Raises:
            ValueError: If provider configuration is invalid or incomplete
            ImportError: If required dependencies are not available
        """
        # Validate configuration completeness
        if not config.is_provider_configured():
            missing = config.get_missing_config()
            raise ValueError(
                f"Incomplete configuration for {config.provider} provider. "
                f"Missing: {', '.join(missing)}"
            )

        # Get provider-specific configuration
        provider_config = config.get_provider_config()

        # Create provider based on type
        if config.provider == "openai":
            return EmbeddingProviderFactory._create_openai_provider(provider_config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    @staticmethod
    def _create_openai_provider(config: dict[str, Any]) -> "OpenAIEmbeddingProvider":
        """Create OpenAI embedding provider."""
        try:
            from chunkhound.embeddings import create_openai_provider
        except ImportError:
            try:
                from embeddings import create_openai_provider
            except ImportError:
                raise ImportError(
                    "Failed to import OpenAI provider. "
                    "Ensure chunkhound.embeddings module is available."
                )

        # Extract OpenAI-specific parameters
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        # Model should come from config, but handle None case safely
        if not model:
            raise ValueError("Model not specified in provider configuration")

        logger.debug(
            f"Creating OpenAI provider: model={model}, "
            f"base_url={base_url}, api_key={'***' if api_key else None}"
        )

        try:
            return create_openai_provider(
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
        except Exception as e:
            raise ValueError(f"Failed to create OpenAI provider: {e}") from e




    @staticmethod
    def get_supported_providers() -> list[str]:
        """
        Get list of supported embedding providers.

        Returns:
            List of supported provider names
        """
        return ["openai"]

    @staticmethod
    def validate_provider_dependencies(provider: str) -> tuple[bool, str | None]:
        """
        Validate that dependencies for a provider are available.

        Args:
            provider: Provider name to validate

        Returns:
            Tuple of (is_available, error_message)
        """
        if provider not in EmbeddingProviderFactory.get_supported_providers():
            return False, f"Unsupported provider: {provider}"

        # Try to import the required create function
        try:
            if provider == "openai":
                from chunkhound.embeddings import create_openai_provider

            return True, None

        except ImportError as e:
            return False, f"Missing dependencies for {provider} provider: {e}"

    @staticmethod
    def create_provider_from_legacy_args(
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ) -> "EmbeddingProvider":
        """
        Create provider from legacy CLI-style arguments.

        This method provides backward compatibility for existing code
        that uses the old argument-based provider creation.

        Args:
            provider: Provider name
            model: Model name
            api_key: API key
            base_url: Base URL
            **kwargs: Additional provider-specific arguments

        Returns:
            Configured embedding provider

        Raises:
            ValueError: If configuration is invalid
        """
        # Create configuration from arguments
        config_dict = {
            "provider": provider,
        }

        if model:
            config_dict["model"] = model
        if api_key:
            config_dict["api_key"] = api_key
        if base_url:
            config_dict["base_url"] = base_url

        # Add any additional kwargs
        config_dict.update(kwargs)

        # Create configuration instance
        try:
            config = EmbeddingConfig(**config_dict)
        except Exception as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Create provider
        return EmbeddingProviderFactory.create_provider(config)

    @staticmethod
    def get_provider_info(provider: str) -> dict[str, Any]:
        """
        Get information about a specific provider.

        Args:
            provider: Provider name

        Returns:
            Dictionary containing provider information

        Raises:
            ValueError: If provider is not supported
        """
        if provider not in EmbeddingProviderFactory.get_supported_providers():
            raise ValueError(f"Unsupported provider: {provider}")

        info = {
            "name": provider,
            "dependencies_available": False,
            "error_message": None,
        }

        # Check dependencies
        available, error = EmbeddingProviderFactory.validate_provider_dependencies(
            provider
        )
        info["dependencies_available"] = available
        if error:
            info["error_message"] = error

        # Provider-specific information
        if provider == "openai":
            info.update(
                {
                    "description": "OpenAI text embedding API",
                    "requires": ["api_key"],
                    "optional": ["base_url", "model"],
                    "default_model": "text-embedding-3-small",
                    "supported_models": [
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "text-embedding-ada-002",
                    ],
                }
            )

        return info
