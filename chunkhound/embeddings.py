"""Embedding providers for ChunkHound - pluggable vector embedding generation."""

import asyncio
import os
import aiohttp
import json

from typing import List, Optional, Protocol, Dict, Any
from dataclasses import dataclass

from loguru import logger

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    openai = None  # type: ignore
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available - install with: uv pip install openai")


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
            raise ImportError("OpenAI package not available. Install with: uv pip install openai")
        
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
            
        if openai is not None:
            self._client = openai.AsyncOpenAI(**client_kwargs)
        else:
            raise ImportError("OpenAI package not available")
        
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


class OpenAICompatibleProvider:
    """Generic OpenAI-compatible embedding provider for any server implementing OpenAI embeddings API."""
    
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
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
        self._base_url = base_url.rstrip('/')
        self._model = model
        self._api_key = api_key
        self._batch_size = batch_size
        self._provider_name = provider_name
        self._timeout = timeout
        
        # Will be auto-detected on first use
        self._dims: Optional[int] = None
        self._distance = "cosine"  # Default for most embedding models
        
        logger.info(f"OpenAI-compatible provider initialized: {self._provider_name} (base_url: {self._base_url}, model: {self._model})")
    
    @property
    def name(self) -> str:
        return self._provider_name
    
    @property
    def model(self) -> str:
        return self._model
    
    @property
    def dims(self) -> int:
        if self._dims is None:
            raise ValueError("Embedding dimensions not yet determined. Call embed() first to auto-detect.")
        return self._dims
    
    @property
    def distance(self) -> str:
        return self._distance
    
    @property
    def batch_size(self) -> int:
        return self._batch_size
    
    async def _detect_model_info(self) -> Optional[Dict[str, Any]]:
        """Try to auto-detect model information from server."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Try to get model info from common endpoints
                endpoints = [
                    f"{self._base_url}/v1/models",
                    f"{self._base_url}/models",
                    f"{self._base_url}/info"
                ]
                
                headers = {"Content-Type": "application/json"}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"
                
                for endpoint in endpoints:
                    try:
                        async with session.get(endpoint, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.debug(f"Model info detected from {endpoint}: {data}")
                                return data
                    except Exception as e:
                        logger.debug(f"Failed to get model info from {endpoint}: {e}")
                        continue
                        
        except Exception as e:
            logger.debug(f"Model auto-detection failed: {e}")
        
        return None

    async def _detect_capabilities(self, sample_embedding: List[float]) -> None:
        """Auto-detect model capabilities from a sample embedding."""
        self._dims = len(sample_embedding)
        logger.info(f"Auto-detected embedding dimensions: {self._dims} for model {self._model}")
        
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
                        logger.info(f"Auto-detected model name: {self._model}")
                elif "model" in model_info:
                    # Direct model field
                    self._model = model_info["model"]
                    logger.info(f"Auto-detected model name: {self._model}")
                elif "models" in model_info and len(model_info["models"]) > 0:
                    # Models array
                    self._model = model_info["models"][0]
                    logger.info(f"Auto-detected model name: {self._model}")
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI-compatible API.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        logger.debug(f"Generating embeddings for {len(texts)} texts using {self.model} at {self._base_url}")
        
        try:
            # Process in batches to respect API limits
            all_embeddings: List[List[float]] = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout)) as session:
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i:i + self.batch_size]
                    logger.debug(f"Processing batch {i//self.batch_size + 1}: {len(batch)} texts")
                    
                    # Prepare request
                    headers = {"Content-Type": "application/json"}
                    if self._api_key:
                        headers["Authorization"] = f"Bearer {self._api_key}"
                    
                    payload = {
                        "model": self.model,
                        "input": batch,
                        "encoding_format": "float"
                    }
                    
                    # Make request to OpenAI-compatible endpoint
                    url = f"{self._base_url}/v1/embeddings"
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"API request failed with status {response.status}: {error_text}")
                        
                        response_data = await response.json()
                        
                        # Extract embeddings from response
                        if "data" not in response_data:
                            raise Exception(f"Invalid response format: missing 'data' field")
                        
                        batch_embeddings = [item["embedding"] for item in response_data["data"]]
                        all_embeddings.extend(batch_embeddings)
                        
                        # Auto-detect dimensions from first embedding
                        if self._dims is None and batch_embeddings:
                            await self._detect_capabilities(batch_embeddings[0])
                        
                        # Add small delay between batches to be respectful
                        if i + self.batch_size < len(texts):
                            await asyncio.sleep(0.1)
            
            logger.info(f"Generated {len(all_embeddings)} embeddings using {self.model}")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings from {self._base_url}: {e}")
            raise


class TEIProvider(OpenAICompatibleProvider):
    """HuggingFace Text Embeddings Inference (TEI) optimized provider."""
    
    def __init__(
        self,
        base_url: str,
        model: Optional[str] = None,
        batch_size: int = 32,  # TEI typically works better with smaller batches
        **kwargs
    ):
        """Initialize TEI provider with TEI-specific optimizations.
        
        Args:
            base_url: TEI server URL (e.g., 'http://localhost:8080')
            model: Model name (will be auto-detected if None)
            batch_size: TEI-optimized batch size (default: 32)
            **kwargs: Additional arguments passed to OpenAICompatibleProvider
        """
        # TEI auto-detection: try to get model info from server
        detected_model = model or "auto-detected"
        
        super().__init__(
            base_url=base_url,
            model=detected_model,
            batch_size=batch_size,
            provider_name="tei",
            **kwargs
        )
        
        logger.info(f"TEI provider initialized with optimized batch size: {batch_size}")
    
    async def _detect_capabilities(self, sample_embedding: List[float]) -> None:
        """TEI-specific capability detection."""
        await super()._detect_capabilities(sample_embedding)
        
        # TEI typically uses cosine similarity
        self._distance = "cosine"
        
        logger.info(f"TEI capabilities detected: dims={self._dims}, distance={self._distance}")


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


def create_openai_compatible_provider(
    base_url: str,
    model: str,
    api_key: Optional[str] = None,
    provider_name: str = "openai-compatible",
    **kwargs
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
        **kwargs
    )


def create_tei_provider(
    base_url: str,
    model: Optional[str] = None,
    **kwargs
) -> TEIProvider:
    """Create a TEI (Text Embeddings Inference) optimized provider.
    
    Args:
        base_url: TEI server URL
        model: Model name (auto-detected if None)
        **kwargs: Additional arguments passed to TEIProvider
        
    Returns:
        Configured TEI embedding provider
    """
    return TEIProvider(
        base_url=base_url,
        model=model,
        **kwargs
    )