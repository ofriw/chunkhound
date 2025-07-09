"""ChunkHound Core Types Package - Common type definitions and aliases.

This package contains type definitions, enums, and type aliases used throughout
the ChunkHound system. These types provide better code clarity, IDE support,
and runtime type checking capabilities.

The types are organized into logical groups:
- Language and file type definitions
- Chunk type enumerations
- Provider and model name types
- Common aliases for better readability
"""

from chunkhound.core.types.common import (
    ByteOffset,
    ChunkId,
    ChunkType,
    Dimensions,
    Distance,
    EmbeddingVector,
    FileId,
    FilePath,
    Language,
    LineNumber,
    ModelName,
    ProviderName,
    Timestamp,
)

__all__ = [
    # Enums
    "ChunkType",
    "Language",
    # String types
    "ProviderName",
    "ModelName",
    "FilePath",
    # Numeric types
    "ChunkId",
    "FileId",
    "LineNumber",
    "ByteOffset",
    "Timestamp",
    "Distance",
    "Dimensions",
    # Complex types
    "EmbeddingVector",
]
