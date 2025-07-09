"""Database providers package for ChunkHound - concrete database implementations."""

from .duckdb_provider import DuckDBProvider

__all__ = [
    "DuckDBProvider",
]
