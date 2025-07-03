"""ChunkHound - Local-first semantic code search with vector and regex capabilities."""

from .version import __version__

__author__ = "Ofri Wolfus"
__description__ = "Local-first semantic code search with vector and regex capabilities"

# Import modules only when needed to avoid dependency issues during setup
__all__ = [
    "Database",
    "CodeParser",
    "Chunker",
    "__version__",
]


def __getattr__(name: str):
    """Lazy import to avoid dependency issues during setup."""
    if name == "Database":
        from .database import Database

        return Database
    elif name == "CodeParser":
        from .parser import CodeParser

        return CodeParser
    elif name == "Chunker":
        from .chunker import Chunker

        return Chunker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
