"""Chunk caching service for content-based chunk comparison and caching."""

from dataclasses import dataclass

from chunkhound.core.models.chunk import Chunk


@dataclass
class ChunkDiff:
    """Represents differences between new and existing chunks for smart updates."""

    unchanged: list[Chunk]  # Chunks with matching content
    modified: list[Chunk]  # Chunks with different content
    added: list[Chunk]  # New chunks not in existing set
    deleted: list[Chunk]  # Existing chunks not in new set


class ChunkCacheService:
    """Service for comparing chunks based on direct content comparison to minimize embedding regeneration."""

    def __init__(self):
        """Initialize chunk cache service."""
        pass

    def diff_chunks(
        self, new_chunks: list[Chunk], existing_chunks: list[Chunk]
    ) -> ChunkDiff:
        """Compare chunks by direct string comparison to identify changes.

        Args:
            new_chunks: Newly parsed chunks from file
            existing_chunks: Currently stored chunks from database

        Returns:
            ChunkDiff object categorizing chunk changes
        """
        # Build content lookup for existing chunks using direct string comparison
        # Use chunk content as key, but handle potential duplicates by using lists
        existing_by_content: dict[str, list[Chunk]] = {}
        for chunk in existing_chunks:
            if chunk.code not in existing_by_content:
                existing_by_content[chunk.code] = []
            existing_by_content[chunk.code].append(chunk)

        # Build content lookup for new chunks
        new_by_content: dict[str, list[Chunk]] = {}
        for chunk in new_chunks:
            if chunk.code not in new_by_content:
                new_by_content[chunk.code] = []
            new_by_content[chunk.code].append(chunk)

        # Find intersections and differences using content strings
        existing_content = set(existing_by_content.keys())
        new_content = set(new_by_content.keys())

        unchanged_content = existing_content & new_content
        deleted_content = existing_content - new_content
        added_content = new_content - existing_content

        # Flatten lists for result
        unchanged_chunks = []
        for content in unchanged_content:
            unchanged_chunks.extend(existing_by_content[content])

        deleted_chunks = []
        for content in deleted_content:
            deleted_chunks.extend(existing_by_content[content])

        added_chunks = []
        for content in added_content:
            added_chunks.extend(new_by_content[content])

        return ChunkDiff(
            unchanged=unchanged_chunks,
            modified=[],  # Still using add/delete approach for simplicity
            added=added_chunks,
            deleted=deleted_chunks,
        )
