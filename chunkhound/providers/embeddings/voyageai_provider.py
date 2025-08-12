"""VoyageAI embedding provider implementation for ChunkHound - concrete embedding provider using VoyageAI API."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from chunkhound.core.exceptions.core import ValidationError
from chunkhound.interfaces.embedding_provider import EmbeddingConfig, RerankResult

from .shared_utils import (
    estimate_tokens_rough,
    chunk_text_by_words, 
    validate_text_input,
    get_usage_stats_dict,
    get_dimensions_for_model,
)

try:
    import voyageai

    VOYAGEAI_AVAILABLE = True
except ImportError:
    voyageai = None  # type: ignore
    VOYAGEAI_AVAILABLE = False
    logger.warning("VoyageAI not available - install with: uv pip install voyageai")


class VoyageAIEmbeddingProvider:
    """VoyageAI embedding provider using voyage-3.5 by default."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "voyage-3.5",
        rerank_model: str = "rerank-lite-1",
        batch_size: int = 100,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        max_tokens: int | None = None,
    ):
        """Initialize VoyageAI embedding provider.

        Args:
            api_key: VoyageAI API key (defaults to VOYAGE_API_KEY env var)
            model: Model name to use for embeddings
            rerank_model: Model name to use for reranking
            batch_size: Maximum batch size for API requests
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Delay between retry attempts
            max_tokens: Maximum tokens per request (if applicable)
        """
        if not VOYAGEAI_AVAILABLE:
            raise ImportError("VoyageAI not available - install with: uv pip install voyageai")

        self._model = model
        self._rerank_model = rerank_model
        self._batch_size = min(batch_size, 1000)  # VoyageAI limit
        self._timeout = timeout
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._max_tokens = max_tokens or 32000  # VoyageAI default context length
        self._api_key = api_key

        # Initialize client
        self._client = voyageai.Client(api_key=api_key)

        # Model dimension mapping
        self._dimensions_map = {
            "voyage-3-large": 1024,
            "voyage-3.5": 1024,
            "voyage-3.5-lite": 1024,
            "voyage-code-3": 1024,
            "voyage-finance-2": 1024,
            "voyage-law-2": 1024,
        }

        # Usage tracking
        self._requests_made = 0
        self._tokens_used = 0
        self._embeddings_generated = 0

    @property
    def name(self) -> str:
        """Provider name."""
        return "voyageai"

    @property
    def model(self) -> str:
        """Model name."""
        return self._model

    @property
    def dims(self) -> int:
        """Embedding dimensions."""
        return get_dimensions_for_model(self._model, self._dimensions_map, default_dims=1024)

    @property
    def distance(self) -> str:
        """Distance metric (VoyageAI uses cosine)."""
        return "cosine"

    @property
    def batch_size(self) -> int:
        """Maximum batch size."""
        return self._batch_size

    @property
    def max_tokens(self) -> int:
        """Maximum tokens per request."""
        return self._max_tokens

    @property
    def config(self) -> EmbeddingConfig:
        """Provider configuration."""
        return EmbeddingConfig(
            provider="voyageai",
            model=self._model,
            dims=self.dims,
            distance=self.distance,
            batch_size=self._batch_size,
            max_tokens=self._max_tokens,
            api_key=self._api_key,
            timeout=self._timeout,
            retry_attempts=self._retry_attempts,
            retry_delay=self._retry_delay,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        validated_texts = validate_text_input(texts)
        
        try:
            result = await asyncio.to_thread(
                self._client.embed,
                texts=validated_texts,
                model=self._model,
                input_type="document",
                truncation=True
            )
            
            self._requests_made += 1
            self._tokens_used += result.total_tokens
            self._embeddings_generated += len(texts)
            
            return [embedding for embedding in result.embeddings]
            
        except Exception as e:
            logger.error(f"VoyageAI embedding failed: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed([text])
        return embeddings[0]

    async def embed_batch(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        """Generate embeddings in batches for optimal performance."""
        if not texts:
            return []

        batch_size = batch_size or self._batch_size
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        
        all_embeddings = []
        for batch in batches:
            embeddings = await self.embed(batch)
            all_embeddings.extend(embeddings)
            
        return all_embeddings

    async def embed_streaming(self, texts: list[str]) -> AsyncIterator[list[float]]:
        """Generate embeddings with streaming results."""
        for text in texts:
            embedding = await self.embed_single(text)
            yield embedding

    async def initialize(self) -> None:
        """Initialize the embedding provider."""
        # Test API connection
        try:
            await self.embed_single("test")
            logger.info(f"VoyageAI provider initialized with model: {self._model}")
        except Exception as e:
            logger.error(f"VoyageAI provider initialization failed: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown the embedding provider and cleanup resources."""
        logger.info("VoyageAI provider shutdown complete")

    def is_available(self) -> bool:
        """Check if the provider is available and properly configured."""
        return VOYAGEAI_AVAILABLE and self._api_key is not None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check and return status information."""
        try:
            await self.embed_single("health check")
            return {
                "status": "healthy",
                "provider": "voyageai",
                "model": self._model,
                "rerank_model": self._rerank_model,
                "dimensions": self.dims,
                "requests_made": self._requests_made,
                "tokens_used": self._tokens_used,
                "embeddings_generated": self._embeddings_generated,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "voyageai",
                "error": str(e),
            }


    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (rough approximation)."""
        return int(estimate_tokens_rough(text))

    def chunk_text_by_tokens(self, text: str, max_tokens: int) -> list[str]:
        """Split text into chunks by token count."""
        return chunk_text_by_words(text, max_tokens)

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the embedding model."""
        return {
            "provider": "voyageai",
            "model": self._model,
            "rerank_model": self._rerank_model,
            "dimensions": self.dims,
            "max_tokens": self._max_tokens,
            "supports_reranking": True,
        }

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return get_usage_stats_dict(
            self._requests_made,
            self._tokens_used, 
            self._embeddings_generated
        )

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self._requests_made = 0
        self._tokens_used = 0
        self._embeddings_generated = 0

    def update_config(self, **kwargs: Any) -> None:
        """Update provider configuration."""
        if "model" in kwargs:
            self._model = kwargs["model"]
        if "rerank_model" in kwargs:
            self._rerank_model = kwargs["rerank_model"]
        if "batch_size" in kwargs:
            self._batch_size = kwargs["batch_size"]
        if "timeout" in kwargs:
            self._timeout = kwargs["timeout"]

    def get_supported_distances(self) -> list[str]:
        """Get list of supported distance metrics."""
        return ["cosine"]  # VoyageAI uses cosine similarity

    def get_optimal_batch_size(self) -> int:
        """Get optimal batch size for this provider."""
        return min(self._batch_size, 100)  # VoyageAI can handle up to 1000, but 100 is optimal

    def get_max_tokens_per_batch(self) -> int:
        """Get maximum tokens per batch for this provider."""
        return self._max_tokens * self._batch_size

    def get_max_documents_per_batch(self) -> int:
        """Get maximum documents per batch for VoyageAI provider."""
        return 1000  # VoyageAI API limit

    # Reranking Operations
    def supports_reranking(self) -> bool:
        """VoyageAI provider supports reranking."""
        return True

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query using VoyageAI reranker."""
        if not documents:
            return []

        try:
            result = await asyncio.to_thread(
                self._client.rerank,
                query=query,
                documents=documents,
                model=self._rerank_model,
                top_k=top_k
            )
            
            self._requests_made += 1
            
            rerank_results = []
            for item in result.results:
                rerank_results.append(RerankResult(
                    index=item.index,
                    score=item.relevance_score
                ))
                
            return rerank_results
            
        except Exception as e:
            logger.error(f"VoyageAI reranking failed: {e}")
            raise RuntimeError(f"Reranking failed: {e}") from e