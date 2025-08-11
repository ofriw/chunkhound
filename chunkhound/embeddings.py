"""Embedding providers for ChunkHound - pluggable vector embedding generation."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import aiohttp
from loguru import logger

# Core domain models

# OpenAI and tiktoken imports have been moved to the specific provider implementations
# that need them. This reduces unnecessary dependencies in the core module.


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    @property
    def name(self) -> str:
        """Provider name (e.g., 'openai')."""
        ...

    @property
    def model(self) -> str:
        """Model name (e.g., 'text-embedding-3-small')."""
        ...

    @property
    def dims(self) -> int:
        """Embedding dimensions."""
        ...

    @property
    def distance(self) -> str:
        """Distance metric ('cosine' | 'l2')."""
        ...

    @property
    def batch_size(self) -> int:
        """Maximum batch size for embedding requests."""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per input text)
        """
        ...


@dataclass
class LocalEmbeddingResult:
    """Local result from embedding operation (legacy)."""

    embeddings: list[list[float]]
    model: str
    provider: str
    dims: int
    total_tokens: int | None = None


# OpenAIEmbeddingProvider has been moved to chunkhound.providers.embeddings.openai_provider
# The old implementation has been removed to avoid duplication and confusion.
# Use create_openai_provider() function below which imports from the new location.


class OpenAICompatibleProvider:
    """Generic OpenAI-compatible embedding provider for any server implementing OpenAI embeddings API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        batch_size: int = 100,
        provider_name: str = "openai-compatible",
        timeout: int = 60,
    ):
        """Initialize OpenAI-compatible embedding provider.

        Args:
            base_url: Base URL for the embedding server (e.g., 'http://localhost:8080')
            model: Model name to use for embeddings
            api_key: Optional API key for authentication
            batch_size: Maximum batch size for API requests
            provider_name: Name for this provider instance
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._batch_size = batch_size
        self._provider_name = provider_name
        self._timeout = timeout

        # Will be auto-detected on first use
        self._dims: int | None = None
        self._distance = "cosine"  # Default for most embedding models

        # Skip logging to avoid interfering with MCP JSON-RPC

    @property
    def name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    @property
    def dims(self) -> int:
        if self._dims is None:
            raise ValueError(
                "Embedding dimensions not yet determined. Call embed() first to auto-detect."
            )
        return self._dims

    @property
    def distance(self) -> str:
        return self._distance

    @property
    def batch_size(self) -> int:
        return self._batch_size

    async def _detect_model_info(self) -> dict[str, Any] | None:
        """Try to auto-detect model information from server."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                # Try to get model info from common endpoints
                endpoints = [
                    f"{self._base_url}/v1/models",
                    f"{self._base_url}/models",
                    f"{self._base_url}/info",
                ]

                headers = {"Content-Type": "application/json"}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"

                for endpoint in endpoints:
                    try:
                        async with session.get(endpoint, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.debug(
                                    f"Model info detected from {endpoint}: {data}"
                                )
                                return data if isinstance(data, dict) else None
                    except Exception as e:
                        logger.debug(f"Failed to get model info from {endpoint}: {e}")
                        continue

        except Exception as e:
            logger.debug(f"Model auto-detection failed: {e}")

        return None

    async def _detect_capabilities(self, sample_embedding: list[float]) -> None:
        """Auto-detect model capabilities from a sample embedding."""
        self._dims = len(sample_embedding)
        logger.debug(
            f"Auto-detected embedding dimensions: {self._dims} for model {self._model}"
        )

        # Try to get additional model info if model was auto-detected
        if self._model == "auto-detected":
            model_info = await self._detect_model_info()
            if model_info:
                # Try to extract model name from various response formats
                if "data" in model_info and len(model_info["data"]) > 0:
                    # OpenAI-style response
                    first_model = model_info["data"][0]
                    if "id" in first_model:
                        self._model = first_model["id"]
                        logger.debug(f"Auto-detected model name: {self._model}")
                elif "model" in model_info:
                    # Direct model field
                    self._model = model_info["model"]
                    logger.info(f"Auto-detected model name: {self._model}")
                elif "models" in model_info and len(model_info["models"]) > 0:
                    # Models array
                    self._model = model_info["models"][0]
                    logger.info(f"Auto-detected model name: {self._model}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI-compatible API.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.debug(
            f"Generating embeddings for {len(texts)} texts using {self.model} at {self._base_url}"
        )

        try:
            # Process in batches to respect API limits
            all_embeddings: list[list[float]] = []

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as session:
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i : i + self.batch_size]
                    logger.debug(
                        f"Processing batch {i // self.batch_size + 1}: {len(batch)} texts"
                    )

                    # Prepare request
                    headers = {"Content-Type": "application/json"}
                    if self._api_key:
                        headers["Authorization"] = f"Bearer {self._api_key}"

                    payload = {
                        "model": self.model,
                        "input": batch,
                        "encoding_format": "float",
                    }

                    # Make request to OpenAI-compatible endpoint
                    url = f"{self._base_url}/v1/embeddings"
                    async with session.post(
                        url, headers=headers, json=payload
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(
                                f"API request failed with status {response.status}: {error_text}"
                            )

                        response_data = await response.json()

                        # Extract embeddings from response
                        if "data" not in response_data:
                            raise Exception(
                                "Invalid response format: missing 'data' field"
                            )

                        batch_embeddings = [
                            item["embedding"] for item in response_data["data"]
                        ]
                        all_embeddings.extend(batch_embeddings)

                        # Auto-detect dimensions from first embedding
                        if self._dims is None and batch_embeddings:
                            await self._detect_capabilities(batch_embeddings[0])

                        # Add small delay between batches to be respectful
                        if i + self.batch_size < len(texts):
                            await asyncio.sleep(0.1)

            logger.debug(
                f"Generated {len(all_embeddings)} embeddings using {self.model}"
            )
            return all_embeddings

        except Exception as e:
            logger.error(f"[Legacy-Embeddings] Failed to generate embeddings from {self._base_url}: {e}")
            raise




class EmbeddingManager:
    """Manages embedding providers and generation."""

    def __init__(self) -> None:
        self._providers: dict[str, EmbeddingProvider] = {}
        self._default_provider: str | None = None

    def register_provider(
        self, provider: EmbeddingProvider, set_default: bool = False
    ) -> None:
        """Register an embedding provider.

        Args:
            provider: The embedding provider to register
            set_default: Whether to set this as the default provider
        """
        self._providers[provider.name] = provider
        logger.info(
            f"Registered embedding provider: {provider.name} (model: {provider.model})"
        )

        if set_default or self._default_provider is None:
            self._default_provider = provider.name
            logger.info(f"Set default embedding provider: {provider.name}")

    def get_provider(self, name: str | None = None) -> EmbeddingProvider:
        """Get an embedding provider by name.

        Args:
            name: Provider name (uses default if None)

        Returns:
            The requested embedding provider
        """
        if name is None:
            if self._default_provider is None:
                raise ValueError("No default embedding provider set")
            name = self._default_provider

        if name not in self._providers:
            raise ValueError(f"Unknown embedding provider: {name}")

        return self._providers[name]

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    async def embed_texts(
        self,
        texts: list[str],
        provider_name: str | None = None,
    ) -> LocalEmbeddingResult:
        """Generate embeddings for texts using specified provider.

        Args:
            texts: List of texts to embed
            provider_name: Provider to use (uses default if None)

        Returns:
            Embedding result with vectors and metadata
        """
        provider = self.get_provider(provider_name)

        embeddings = await provider.embed(texts)

        return LocalEmbeddingResult(
            embeddings=embeddings,
            model=provider.model,
            provider=provider.name,
            dims=provider.dims,
        )


def create_openai_provider(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = "text-embedding-3-small",
) -> "OpenAIEmbeddingProvider":
    """Create an OpenAI embedding provider with default settings.

    Args:
        api_key: OpenAI API key (uses OPENAI_API_KEY env var if None)
        base_url: Base URL for API (uses OPENAI_BASE_URL env var if None)
        model: Model name to use

    Returns:
        Configured OpenAI embedding provider
    """
    # Import the new provider from the correct location
    from chunkhound.providers.embeddings.openai_provider import OpenAIEmbeddingProvider

    return OpenAIEmbeddingProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def create_openai_compatible_provider(
    base_url: str,
    model: str,
    api_key: str | None = None,
    provider_name: str = "openai-compatible",
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    """Create a generic OpenAI-compatible embedding provider.

    Args:
        base_url: Base URL for the embedding server
        model: Model name to use for embeddings
        api_key: Optional API key for authentication
        provider_name: Name for this provider instance
        **kwargs: Additional arguments passed to OpenAICompatibleProvider

    Returns:
        Configured OpenAI-compatible embedding provider
    """
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        provider_name=provider_name,
        **kwargs,
    )










