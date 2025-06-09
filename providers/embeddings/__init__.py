"""Embedding providers package for ChunkHound - concrete embedding implementations."""

from .openai_provider import OpenAIEmbeddingProvider

__all__ = [
    "OpenAIEmbeddingProvider",
]