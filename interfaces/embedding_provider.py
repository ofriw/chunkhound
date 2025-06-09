"""EmbeddingProvider protocol for ChunkHound - abstract interface for embedding implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol, Dict, Any, AsyncIterator
from dataclasses import dataclass

from core.models import Embedding, EmbeddingResult


@dataclass
class EmbeddingConfig:
    """Configuration for embedding providers."""
    provider: str
    model: str
    dims: int
    distance: str = "cosine"
    batch_size: int = 100
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


class EmbeddingProvider(Protocol):
    """Abstract protocol for embedding providers.
    
    Defines the interface that all embedding implementations must follow.
    This enables pluggable embedding backends (OpenAI, BGE, local models, etc.)
    """
    
    @property
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'bge', 'local')."""
        ...
    
    @property
    def model(self) -> str:
        """Model name (e.g., 'text-embedding-3-small', 'bge-in-icl')."""
        ...
    
    @property
    def dims(self) -> int:
        """Embedding dimensions."""
        ...
    
    @property
    def distance(self) -> str:
        """Distance metric ('cosine' | 'l2' | 'ip')."""
        ...
    
    @property
    def batch_size(self) -> int:
        """Maximum batch size for embedding requests."""
        ...
    
    @property
    def max_tokens(self) -> Optional[int]:
        """Maximum tokens per request (if applicable)."""
        ...
    
    @property
    def config(self) -> EmbeddingConfig:
        """Provider configuration."""
        ...
    
    # Core Embedding Operations
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text)
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
    
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
    
    async def embed_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Generate embeddings in batches for optimal performance.
        
        Args:
            texts: List of text strings to embed
            batch_size: Optional batch size override
            
        Returns:
            List of embedding vectors (one per input text)
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
    
    async def embed_streaming(self, texts: List[str]) -> AsyncIterator[List[float]]:
        """Generate embeddings with streaming results.
        
        Args:
            texts: List of text strings to embed
            
        Yields:
            Embedding vectors one at a time
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
    
    # Provider Management
    async def initialize(self) -> None:
        """Initialize the embedding provider (load models, validate API keys, etc.)."""
        ...
    
    async def shutdown(self) -> None:
        """Shutdown the embedding provider and cleanup resources."""
        ...
    
    def is_available(self) -> bool:
        """Check if the provider is available and properly configured."""
        ...
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status information."""
        ...
    
    # Validation and Preprocessing
    def validate_texts(self, texts: List[str]) -> List[str]:
        """Validate and preprocess texts before embedding.
        
        Args:
            texts: List of text strings to validate
            
        Returns:
            List of validated/preprocessed texts
            
        Raises:
            ValidationError: If texts are invalid
        """
        ...
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text (if applicable).
        
        Args:
            text: Text string to analyze
            
        Returns:
            Estimated token count
        """
        ...
    
    def chunk_text_by_tokens(self, text: str, max_tokens: int) -> List[str]:
        """Split text into chunks by token count (if applicable).
        
        Args:
            text: Text string to chunk
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List of text chunks
        """
        ...
    
    # Metadata and Information
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        ...
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics (tokens used, requests made, etc.)."""
        ...
    
    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        ...
    
    # Configuration Management
    def update_config(self, **kwargs) -> None:
        """Update provider configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        ...
    
    def get_supported_distances(self) -> List[str]:
        """Get list of supported distance metrics."""
        ...
    
    def get_optimal_batch_size(self) -> int:
        """Get optimal batch size for this provider."""
        ...


class LocalEmbeddingProvider(EmbeddingProvider, Protocol):
    """Extended protocol for local embedding providers."""
    
    @property
    def model_path(self) -> str:
        """Path to the local model."""
        ...
    
    @property
    def device(self) -> str:
        """Device used for inference ('cpu', 'cuda', 'mps')."""
        ...
    
    def load_model(self) -> None:
        """Load the embedding model into memory."""
        ...
    
    def unload_model(self) -> None:
        """Unload the embedding model from memory."""
        ...
    
    def is_model_loaded(self) -> bool:
        """Check if the model is loaded in memory."""
        ...


class APIEmbeddingProvider(EmbeddingProvider, Protocol):
    """Extended protocol for API-based embedding providers."""
    
    @property
    def api_key(self) -> Optional[str]:
        """API key for authentication."""
        ...
    
    @property
    def base_url(self) -> str:
        """Base URL for API requests."""
        ...
    
    @property
    def timeout(self) -> int:
        """Request timeout in seconds."""
        ...
    
    @property
    def retry_attempts(self) -> int:
        """Number of retry attempts for failed requests."""
        ...
    
    async def validate_api_key(self) -> bool:
        """Validate API key with the service."""
        ...
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limit information."""
        ...
    
    def get_request_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        ...