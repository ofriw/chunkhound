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
                                "Invalid BGE-IN-ICL response format: missing 'data' field"
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
            logger.error(f"Failed to generate embeddings from {self._base_url}: {e}")
            raise


class TEIProvider(OpenAICompatibleProvider):
    """HuggingFace Text Embeddings Inference (TEI) optimized provider."""

    def __init__(
        self,
        base_url: str,
        model: str | None = None,
        batch_size: int = 32,  # TEI typically works better with smaller batches
        **kwargs: Any,
    ) -> None:
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
            **kwargs,
        )

        logger.info(f"TEI provider initialized with optimized batch size: {batch_size}")

    async def _detect_capabilities(self, sample_embedding: list[float]) -> None:
        """TEI-specific capability detection."""
        await super()._detect_capabilities(sample_embedding)

        # TEI typically uses cosine similarity
        self._distance = "cosine"

        logger.info(
            f"TEI capabilities detected: dims={self._dims}, distance={self._distance}"
        )


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


def create_tei_provider(
    base_url: str, model: str | None = None, **kwargs: Any
) -> TEIProvider:
    """Create a TEI (Text Embeddings Inference) optimized provider.

    Args:
        base_url: TEI server URL
        model: Model name (auto-detected if None)
        **kwargs: Additional arguments passed to TEIProvider

    Returns:
        Configured TEI embedding provider
    """
    return TEIProvider(base_url=base_url, model=model, **kwargs)


@dataclass
class PerformanceMetrics:
    """Performance metrics for BGE-IN-ICL operations."""

    total_requests: int = 0
    total_texts: int = 0
    total_time: float = 0.0
    total_context_time: float = 0.0
    batch_sizes: list[int] = field(default_factory=list)
    response_times: list[float] = field(default_factory=list)
    context_hits: int = 0
    context_misses: int = 0

    @property
    def avg_texts_per_second(self) -> float:
        return self.total_texts / max(self.total_time, 0.001)

    @property
    def avg_response_time(self) -> float:
        return sum(self.response_times) / max(len(self.response_times), 1)

    @property
    def cache_hit_rate(self) -> float:
        total_cache_requests = self.context_hits + self.context_misses
        return self.context_hits / max(total_cache_requests, 1)


class ICLContextManager:
    """Manages in-context learning examples and templates for BGE-IN-ICL with advanced optimization."""

    def __init__(self, cache_size: int = 100, similarity_threshold: float = 0.8):
        """Initialize ICL context manager.

        Args:
            cache_size: Maximum number of cached context templates
            similarity_threshold: Minimum similarity score for context reuse
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_size = cache_size
        self._similarity_threshold = similarity_threshold
        self._context_scores: dict[str, float] = {}  # Track context quality scores

        # Default context templates for different programming languages
        self._language_templates = {
            "python": {
                "instruction": "Generate embeddings for Python code with understanding of classes, functions, and imports.",
                "examples": [
                    "class DataProcessor:\n    def process(self, data):\n        return data.strip()",
                    "def calculate_metrics(values: List[float]) -> Dict[str, float]:\n    return {'mean': sum(values) / len(values)}",
                ],
            },
            "javascript": {
                "instruction": "Generate embeddings for JavaScript code with understanding of functions, objects, and async patterns.",
                "examples": [
                    "async function fetchData(url) {\n    const response = await fetch(url);\n    return response.json();\n}",
                    "const userService = {\n    async getUser(id) {\n        return this.api.get(`/users/${id}`);\n    }\n};",
                ],
            },
            "typescript": {
                "instruction": "Generate embeddings for TypeScript code with understanding of types, interfaces, and generics.",
                "examples": [
                    "interface User {\n    id: number;\n    name: string;\n    email: string;\n}",
                    "function processItems<T>(items: T[], processor: (item: T) => T): T[] {\n    return items.map(processor);\n}",
                ],
            },
            "java": {
                "instruction": "Generate embeddings for Java code with understanding of classes, methods, and annotations.",
                "examples": [
                    "@Service\npublic class UserService {\n    @Autowired\n    private UserRepository repository;\n}",
                    "public class Calculator {\n    public int add(int a, int b) {\n        return a + b;\n    }\n}",
                ],
            },
            "csharp": {
                "instruction": "Generate embeddings for C# code with understanding of classes, properties, and LINQ.",
                "examples": [
                    "public class User {\n    public int Id { get; set; }\n    public string Name { get; set; }\n}",
                    "public async Task<List<User>> GetActiveUsersAsync() {\n    return await context.Users.Where(u => u.IsActive).ToListAsync();\n}",
                ],
            },
            "generic": {
                "instruction": "Generate embeddings for code with semantic understanding of programming constructs.",
                "examples": [
                    "function process(data) {\n    return data.map(item => transform(item));\n}",
                    "class Handler {\n    execute(request) {\n        return this.process(request.data);\n    }\n}",
                ],
            },
        }

    def get_context_for_language(self, language: str, text: str) -> dict[str, Any]:
        """Get ICL context for a specific programming language with similarity scoring.

        Args:
            language: Programming language (python, javascript, etc.)
            text: The text to be embedded

        Returns:
            Context dictionary with instruction and examples
        """
        # Use language-specific template or fallback to generic
        template = self._language_templates.get(
            language.lower(), self._language_templates["generic"]
        )

        # Create cache key
        cache_key = f"{language}:{hash(text[:100])}"

        # Check cache first with similarity scoring
        if cache_key in self._cache:
            cached_context = self._cache[cache_key]
            # Check if cached context is still relevant
            similarity_score = self._calculate_context_similarity(
                text, cached_context.get("target_text", "")
            )
            if similarity_score >= self._similarity_threshold:
                return cached_context

        # Select best examples using similarity scoring
        selected_examples = self._select_best_examples(
            list(template["examples"]), text, language
        )

        # Create optimized context
        context = {
            "instruction": template["instruction"],
            "examples": selected_examples,
            "target_text": text[
                :200
            ],  # Include snippet of target text for better context
            "language": language,
            "similarity_score": 1.0,  # New context gets max score
            "timestamp": time.time(),
        }

        # Cache result with LRU eviction
        self._update_cache(cache_key, context)
        return context

    def _calculate_context_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text contexts using simple heuristics.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0

        # Simple token-based similarity
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _select_best_examples(
        self, examples: list[str], target_text: str, language: str
    ) -> list[str]:
        """Select the most relevant examples based on similarity to target text.

        Args:
            examples: Available examples for the language
            target_text: The text being embedded
            language: Programming language

        Returns:
            List of best examples (up to 2)
        """
        if len(examples) <= 2:
            return examples

        # Score each example based on similarity to target
        scored_examples = []
        for example in examples:
            similarity = self._calculate_context_similarity(target_text, example)
            scored_examples.append((similarity, example))

        # Sort by similarity and take top 2
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        return [example for _, example in scored_examples[:2]]

    def _update_cache(self, cache_key: str, context: dict[str, Any]) -> None:
        """Update cache with LRU eviction and quality scoring.

        Args:
            cache_key: Cache key
            context: Context to cache
        """
        # Remove old entry if it exists
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Evict least recently used if cache is full
        if len(self._cache) >= self._cache_size:
            # Find oldest entry by timestamp
            oldest_key = min(
                self._cache.keys(), key=lambda k: self._cache[k].get("timestamp", 0)
            )
            del self._cache[oldest_key]
            if oldest_key in self._context_scores:
                del self._context_scores[oldest_key]

        # Add new entry
        self._cache[cache_key] = context
        self._context_scores[cache_key] = context.get("similarity_score", 0.0)

    def get_generic_context(self, text: str) -> dict[str, Any]:
        """Get generic ICL context for any text.

        Args:
            text: The text to be embedded

        Returns:
            Generic context dictionary
        """
        return self.get_context_for_language("generic", text)


class BGEInICLProvider:
    """BGE-IN-ICL (Background Generation Enhanced with In-Context Learning) embedding provider.

    Supports BAAI's BGE-IN-ICL model with in-context learning capabilities for enhanced
    code understanding and semantic embeddings. Features advanced optimization including
    dynamic context selection, adaptive batching, and performance monitoring.
    """

    def __init__(
        self,
        base_url: str,
        model: str = "bge-in-icl",
        api_key: str | None = None,
        batch_size: int = 50,
        timeout: int = 120,
        language: str = "auto",
        enable_icl: bool = True,
        context_cache_size: int = 100,
        adaptive_batching: bool = True,
        min_batch_size: int = 10,
        max_batch_size: int = 100,
    ):
        """Initialize BGE-IN-ICL embedding provider with advanced features.

        Args:
            base_url: Base URL for the BGE-IN-ICL server
            model: Model name (default: bge-in-icl)
            api_key: Optional API key for authentication
            batch_size: Initial batch size (will be adapted if adaptive_batching=True)
            timeout: Request timeout in seconds (longer for ICL processing)
            language: Programming language for context templates ('auto', 'python', etc.)
            enable_icl: Whether to enable in-context learning features
            context_cache_size: Size of the context cache
            adaptive_batching: Whether to enable adaptive batch sizing
            min_batch_size: Minimum batch size for adaptive batching
            max_batch_size: Maximum batch size for adaptive batching
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._batch_size = batch_size
        self._timeout = timeout
        self._language = language
        self._enable_icl = enable_icl
        self._adaptive_batching = adaptive_batching
        self._min_batch_size = min_batch_size

        # UNIFIED BATCHING SYSTEM: For adaptive batching, allow growth up to max_batch_size
        # For non-adaptive batching, respect user-configured batch_size as maximum
        if adaptive_batching:
            self._max_batch_size = max_batch_size
        else:
            # If user specified a batch_size, use it as the max_batch_size to ensure
            # non-adaptive batching never exceeds the user's intended limit
            self._max_batch_size = min(max_batch_size, batch_size)

        # Initialize context manager with similarity scoring
        self._context_manager = ICLContextManager(cache_size=context_cache_size)

        # Performance monitoring
        self._metrics = PerformanceMetrics()
        self._performance_window: list[
            float
        ] = []  # Recent response times for adaptive batching
        self._window_size = 10  # Number of recent requests to consider

        # Will be auto-detected on first use
        self._dims: int | None = None
        self._distance = "cosine"  # BGE models typically use cosine similarity

        logger.info(
            f"BGE-IN-ICL provider initialized: {self._model} (base_url: {self._base_url}, "
            f"ICL: {self._enable_icl}, adaptive_batching: {self._adaptive_batching})"
        )

        if self._adaptive_batching:
            logger.info(
                f"BGE-IN-ICL adaptive batching: batch_size={self._batch_size}, "
                f"min={self._min_batch_size}, max={self._max_batch_size}"
            )
            if self._max_batch_size < max_batch_size:
                logger.info(
                    f"BGE-IN-ICL respecting user batch limit: {self._max_batch_size} "
                    f"(user-configured) vs {max_batch_size} (default)"
                )

    @property
    def name(self) -> str:
        return "bge-in-icl"

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

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get current performance metrics.

        Returns:
            Dictionary containing performance statistics
        """
        return {
            "total_requests": self._metrics.total_requests,
            "total_texts": self._metrics.total_texts,
            "total_time": self._metrics.total_time,
            "avg_texts_per_second": self._metrics.avg_texts_per_second,
            "avg_response_time": self._metrics.avg_response_time,
            "cache_hit_rate": self._metrics.cache_hit_rate,
            "current_batch_size": self._batch_size,
            "adaptive_batching_enabled": self._adaptive_batching,
            "recent_batch_sizes": self._metrics.batch_sizes[
                -10:
            ],  # Last 10 batch sizes
        }

    def _adapt_batch_size(self, response_time: float) -> None:
        """Adapt batch size based on recent performance.

        Args:
            response_time: Time taken for the last request
        """
        if not self._adaptive_batching:
            return

        # Add to performance window
        self._performance_window.append(response_time)
        if len(self._performance_window) > self._window_size:
            self._performance_window.pop(0)

        # Need at least 3 data points to make decisions
        if len(self._performance_window) < 3:
            return

        avg_response_time = sum(self._performance_window) / len(
            self._performance_window
        )
        recent_response_time = sum(self._performance_window[-3:]) / 3

        # If recent performance is significantly worse, reduce batch size
        if (
            recent_response_time > avg_response_time * 1.5
            and self._batch_size > self._min_batch_size
        ):
            new_size = max(self._min_batch_size, int(self._batch_size * 0.8))
            if new_size != self._batch_size:
                logger.info(
                    f"Reducing batch size from {self._batch_size} to {new_size} "
                    f"(avg_time: {avg_response_time:.2f}s, recent: {recent_response_time:.2f}s)"
                )
                self._batch_size = new_size

        # If recent performance is consistently good, try increasing batch size
        elif (
            recent_response_time < avg_response_time * 0.7
            and self._batch_size < self._max_batch_size
        ):
            new_size = min(self._max_batch_size, int(self._batch_size * 1.2))
            if new_size != self._batch_size:
                logger.info(
                    f"Increasing batch size from {self._batch_size} to {new_size} "
                    f"(avg_time: {avg_response_time:.2f}s, recent: {recent_response_time:.2f}s)"
                )
                self._batch_size = new_size

    def _detect_language(self, text: str) -> str:
        """Detect programming language from text content.

        Args:
            text: Text to analyze

        Returns:
            Detected language or 'generic'
        """
        if self._language != "auto":
            return self._language

        # Simple heuristic language detection - order matters for specificity

        # TypeScript (check before JavaScript for more specific patterns)
        if any(
            keyword in text
            for keyword in [
                "interface ",
                "type ",
                ": string",
                ": number",
                "<T>",
                "function process<",
            ]
        ):
            return "typescript"

        # C# (check for C#-specific patterns before Java since both use 'public class')
        elif any(
            keyword in text
            for keyword in [
                "using System",
                "get; set;",
                "public async Task",
                "namespace ",
                "{ get; set; }",
            ]
        ):
            return "csharp"

        # Java (check for Java-specific patterns)
        elif any(
            keyword in text
            for keyword in [
                "@Override",
                "public static",
                "@Autowired",
                "@Service",
                "import java",
            ]
        ):
            return "java"

        # Python (check for Python-specific patterns)
        elif any(
            keyword in text
            for keyword in ["def ", "class ", "import ", "__init__", "self."]
        ):
            return "python"

        # JavaScript (more general patterns, checked after TypeScript)
        elif any(
            keyword in text
            for keyword in ["function ", "const ", "let ", "async ", "=>", "await "]
        ):
            return "javascript"

        else:
            return "generic"

    def _prepare_icl_request(self, texts: list[str]) -> dict[str, Any]:
        """Prepare request payload with optimized in-context learning data.

        Args:
            texts: List of texts to embed

        Returns:
            Request payload with ICL context and performance tracking
        """
        context_start_time = time.time()

        if not self._enable_icl:
            # Standard request without ICL
            return {"model": self._model, "input": texts, "encoding_format": "float"}

        # Detect language from first text sample
        sample_text = " ".join(texts[:3])  # Use first few texts for language detection
        detected_language = self._detect_language(sample_text)

        # Get optimized context for the detected language
        context = self._context_manager.get_context_for_language(
            detected_language, sample_text
        )

        # Track context processing time
        context_time = time.time() - context_start_time
        self._metrics.total_context_time += context_time

        # Track cache performance
        if "timestamp" in context and context["timestamp"] < time.time() - 1:
            self._metrics.context_hits += 1
        else:
            self._metrics.context_misses += 1

        # Create ICL-enhanced request with quality metrics
        return {
            "model": self._model,
            "input": texts,
            "encoding_format": "float",
            "icl_context": {
                "instruction": context["instruction"],
                "examples": context["examples"],
                "language": detected_language,
                "enable_context_learning": True,
                "similarity_score": context.get("similarity_score", 1.0),
                "context_processing_time": context_time,
            },
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using BGE-IN-ICL with advanced optimization features.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        start_time = time.time()
        self._metrics.total_requests += 1
        self._metrics.total_texts += len(texts)

        logger.debug(
            f"Generating BGE-IN-ICL embeddings for {len(texts)} texts "
            f"(ICL: {self._enable_icl}, adaptive_batching: {self._adaptive_batching})"
        )

        try:
            all_embeddings: list[list[float]] = []

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as session:
                batch_count = 0
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i : i + self.batch_size]
                    batch_start_time = time.time()
                    batch_count += 1

                    logger.debug(
                        f"Processing BGE-IN-ICL batch {batch_count}: {len(batch)} texts "
                        f"(batch_size: {self.batch_size})"
                    )

                    # Prepare headers
                    headers = {"Content-Type": "application/json"}
                    if self._api_key:
                        headers["Authorization"] = f"Bearer {self._api_key}"

                    # Prepare ICL-enhanced payload with performance tracking
                    payload = self._prepare_icl_request(batch)

                    # Make request to BGE-IN-ICL endpoint
                    url = f"{self._base_url}/v1/embeddings"
                    async with session.post(
                        url, headers=headers, json=payload
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(
                                f"BGE-IN-ICL API request failed with status {response.status}: {error_text}"
                            )

                        response_data = await response.json()

                        # Extract embeddings from response
                        if "data" not in response_data:
                            raise Exception(
                                "Invalid OpenAI-compatible response format: missing 'data' field"
                            )

                        batch_embeddings = [
                            item["embedding"] for item in response_data["data"]
                        ]
                        all_embeddings.extend(batch_embeddings)

                        # Performance monitoring and adaptive batching
                        batch_time = time.time() - batch_start_time
                        self._metrics.response_times.append(batch_time)
                        self._metrics.batch_sizes.append(len(batch))

                        # Adapt batch size based on performance
                        self._adapt_batch_size(batch_time)

                        # Auto-detect dimensions from first embedding
                        if self._dims is None and batch_embeddings:
                            self._dims = len(batch_embeddings[0])
                            logger.debug(
                                f"Auto-detected BGE-IN-ICL embedding dimensions: {self._dims}"
                            )

                        # Enhanced ICL logging with performance metrics
                        if self._enable_icl and "icl_info" in response_data:
                            icl_info = response_data["icl_info"]
                            context_score = payload.get("icl_context", {}).get(
                                "similarity_score", 0.0
                            )
                            logger.debug(
                                f"ICL context used: {icl_info.get('language', 'unknown')} "
                                f"with {len(icl_info.get('examples', []))} examples "
                                f"(similarity: {context_score:.3f}, batch_time: {batch_time:.2f}s)"
                            )

                        # Dynamic delay based on performance
                        if i + self.batch_size < len(texts):
                            # Shorter delay if performance is good, longer if struggling
                            delay = 0.1 if batch_time < 2.0 else 0.3
                            await asyncio.sleep(delay)

            # Update total performance metrics
            total_time = time.time() - start_time
            self._metrics.total_time += total_time

            # Log performance summary
            texts_per_second = len(texts) / max(total_time, 0.001)
            cache_hit_rate = self._metrics.cache_hit_rate

            logger.debug(
                f"Generated {len(all_embeddings)} BGE-IN-ICL embeddings using {self._model} "
                f"(ICL: {self._enable_icl}, {texts_per_second:.1f} texts/s, "
                f"cache_hit_rate: {cache_hit_rate:.3f}, batches: {batch_count})"
            )

            return all_embeddings

        except Exception as e:
            # Update error metrics
            error_time = time.time() - start_time
            self._metrics.total_time += error_time
            logger.error(
                f"Failed to generate BGE-IN-ICL embeddings from {self._base_url}: {e}"
            )
            raise


def create_bge_in_icl_provider(
    base_url: str,
    model: str = "bge-in-icl",
    api_key: str | None = None,
    language: str = "auto",
    enable_icl: bool = True,
    adaptive_batching: bool = True,
    min_batch_size: int = 10,
    max_batch_size: int = 100,
    batch_size: int | None = None,
    context_cache_size: int = 100,
    **kwargs: Any,
) -> BGEInICLProvider:
    """Create a BGE-IN-ICL embedding provider with advanced in-context learning features.

    Args:
        base_url: BGE-IN-ICL server URL
        model: Model name (default: bge-in-icl)
        api_key: Optional API key for authentication
        language: Programming language for context ('auto', 'python', etc.)
        enable_icl: Enable in-context learning features
        adaptive_batching: Enable adaptive batch sizing based on performance
        min_batch_size: Minimum batch size for adaptive batching
        max_batch_size: Maximum batch size for adaptive batching (if no batch_size specified)
        batch_size: User-configured batch size (overrides max_batch_size if specified)
        context_cache_size: Size of the context cache for ICL optimization
        **kwargs: Additional arguments passed to BGEInICLProvider

    Returns:
        Configured BGE-IN-ICL embedding provider with Phase 3 advanced features
    """
    # Use user-configured batch_size or default
    effective_batch_size = batch_size if batch_size is not None else 50

    return BGEInICLProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        batch_size=effective_batch_size,
        language=language,
        enable_icl=enable_icl,
        adaptive_batching=adaptive_batching,
        min_batch_size=min_batch_size,
        max_batch_size=max_batch_size,
        context_cache_size=context_cache_size,
        **kwargs,
    )
