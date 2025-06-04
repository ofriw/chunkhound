"""Embedding providers for ChunkHound - pluggable vector embedding generation."""

import asyncio
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Protocol, Dict, Any
from dataclasses import dataclass

from loguru import logger

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available - install with: pip install openai")


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
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text)
        """
        ...


@dataclass
class EmbeddingResult:
    """Result from embedding operation."""
    embeddings: List[List[float]]
    model: str
    provider: str
    dims: int
    total_tokens: Optional[int] = None


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider using text-embedding-3-small by default."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        batch_size: int = 100,
    ):
        """Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Base URL for OpenAI API (defaults to OPENAI_BASE_URL env var)
            model: Model name to use for embeddings
            batch_size: Maximum batch size for API requests
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not available. Install with: pip install openai")
        
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._model = model
        self._batch_size = batch_size
        
        if not self._api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        # Initialize OpenAI client
        client_kwargs: Dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
            
        self._client = openai.AsyncOpenAI(**client_kwargs)
        
        # Model dimensions mapping
        self._model_dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        logger.info(f"OpenAI embedding provider initialized with model: {self._model}")
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def dims(self) -> int:
        return self._model_dims.get(self._model, 1536)
    
    @property
    def distance(self) -> str:
        return "cosine"
    
    @property
    def batch_size(self) -> int:
        return self._batch_size
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        logger.debug(f"Generating embeddings for {len(texts)} texts using {self.model}")
        
        try:
            # Process in batches to respect API limits
            all_embeddings: List[List[float]] = []
            
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                logger.debug(f"Processing batch {i//self.batch_size + 1}: {len(batch)} texts")
                
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                    encoding_format="float"
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Add small delay between batches to be respectful
                if i + self.batch_size < len(texts):
                    await asyncio.sleep(0.1)
            
            logger.info(f"Generated {len(all_embeddings)} embeddings using {self.model}")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise


class EmbeddingManager:
    """Manages embedding providers and generation."""
    
    def __init__(self):
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._default_provider: Optional[str] = None
    
    def register_provider(self, provider: EmbeddingProvider, set_default: bool = False) -> None:
        """Register an embedding provider.
        
        Args:
            provider: The embedding provider to register
            set_default: Whether to set this as the default provider
        """
        self._providers[provider.name] = provider
        logger.info(f"Registered embedding provider: {provider.name} (model: {provider.model})")
        
        if set_default or self._default_provider is None:
            self._default_provider = provider.name
            logger.info(f"Set default embedding provider: {provider.name}")
    
    def get_provider(self, name: Optional[str] = None) -> EmbeddingProvider:
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
    
    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())
    
    async def embed_texts(
        self,
        texts: List[str],
        provider_name: Optional[str] = None,
    ) -> EmbeddingResult:
        """Generate embeddings for texts using specified provider.
        
        Args:
            texts: List of texts to embed
            provider_name: Provider to use (uses default if None)
            
        Returns:
            Embedding result with vectors and metadata
        """
        provider = self.get_provider(provider_name)
        
        embeddings = await provider.embed(texts)
        
        return EmbeddingResult(
            embeddings=embeddings,
            model=provider.model,
            provider=provider.name,
            dims=provider.dims,
        )


def create_openai_provider(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "text-embedding-3-small",
) -> OpenAIEmbeddingProvider:
    """Create an OpenAI embedding provider with default settings.
    
    Args:
        api_key: OpenAI API key (uses OPENAI_API_KEY env var if None)
        base_url: Base URL for API (uses OPENAI_BASE_URL env var if None)
        model: Model name to use
        
    Returns:
        Configured OpenAI embedding provider
    """
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )