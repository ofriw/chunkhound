"""ChunkHound Core Models Package - Domain model definitions.

This package contains the core domain models that represent the fundamental
entities in the ChunkHound system. These models are designed to be independent
of infrastructure concerns and provide a clean, typed interface for working
with files, chunks, and embeddings.

The models follow these principles:
- Immutable data structures using dataclasses with frozen=True
- Rich type hints for better IDE support and runtime validation
- Clear separation between domain logic and persistence concerns
- Backward compatibility with existing dictionary-based interfaces
"""

from chunkhound.core.models.chunk import Chunk
from chunkhound.core.models.embedding import Embedding, EmbeddingResult
from chunkhound.core.models.file import File

__all__ = [
    "File",
    "Chunk",
    "Embedding",
    "EmbeddingResult",
]
