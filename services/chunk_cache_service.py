"""Chunk caching service for content-based chunk comparison and caching."""

from dataclasses import dataclass
from typing import Any

from core.models.chunk import Chunk


@dataclass
class ChunkDiff:
    """Represents differences between new and existing chunks for smart updates."""
    unchanged: list[Chunk]  # Chunks with matching content
    modified: list[Chunk]   # Chunks with different content  
    added: list[Chunk]      # New chunks not in existing set
    deleted: list[Chunk]    # Existing chunks not in new set


class ChunkCacheService:
    """Service for comparing chunks based on direct content comparison to minimize embedding regeneration."""

    def __init__(self):
        """Initialize chunk cache service."""
        pass

    def diff_chunks(
        self, 
        new_chunks: list[Chunk], 
        existing_chunks: list[Chunk]
    ) -> ChunkDiff:
        """Compare chunks by direct string comparison to identify changes.
        
        Args:
            new_chunks: Newly parsed chunks from file
            existing_chunks: Currently stored chunks from database
            
        Returns:
            ChunkDiff object categorizing chunk changes
        """
        # Build content lookup for existing chunks using direct string comparison
        existing_by_content: dict[str, Chunk] = {}
        for chunk in existing_chunks:
            existing_by_content[chunk.code] = chunk

        # Build content lookup for new chunks  
        new_by_content: dict[str, Chunk] = {}
        for chunk in new_chunks:
            new_by_content[chunk.code] = chunk

        # Find intersections and differences using content strings
        existing_content = set(existing_by_content.keys())
        new_content = set(new_by_content.keys())

        unchanged_content = existing_content & new_content
        deleted_content = existing_content - new_content
        added_content = new_content - existing_content

        return ChunkDiff(
            unchanged=[existing_by_content[content] for content in unchanged_content],
            modified=[],  # For now, we consider all changes as add/delete
            added=[new_by_content[content] for content in added_content], 
            deleted=[existing_by_content[content] for content in deleted_content]
        )