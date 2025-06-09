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

from .common import (
    ChunkType,
    Language,
    ProviderName,
    ModelName,
    FilePath,
    ChunkId,
    FileId,
    EmbeddingVector,
    LineNumber,
    ByteOffset,
    Timestamp,
    Distance,
    Dimensions
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