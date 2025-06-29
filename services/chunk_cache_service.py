"""Chunk caching service for content-based chunk comparison and caching."""

import zlib
from dataclasses import dataclass
from typing import Any

from core.models.chunk import Chunk


@dataclass
class ChunkDiff:
    """Represents differences between new and existing chunks for smart updates."""
    unchanged: list[Chunk]  # Chunks with matching content hash
    modified: list[Chunk]   # Chunks with different content
    added: list[Chunk]      # New chunks not in existing set
    deleted: list[Chunk]    # Existing chunks not in new set


class ChunkCacheService:
    """Service for comparing chunks based on content hash to minimize embedding regeneration."""

    def __init__(self):
        """Initialize chunk cache service."""
        pass

    def compute_chunk_hash(self, chunk: Chunk) -> int:
        """Compute stable CRC32 hash of normalized chunk content.
        
        Args:
            chunk: Chunk to hash
            
        Returns:
            CRC32 hash as signed 32-bit integer
        """
        return chunk.compute_content_hash()

    def diff_chunks(
        self, 
        new_chunks: list[Chunk], 
        existing_chunks: list[Chunk]
    ) -> ChunkDiff:
        """Compare chunks by content hash to identify changes.
        
        Args:
            new_chunks: Newly parsed chunks from file
            existing_chunks: Currently stored chunks from database
            
        Returns:
            ChunkDiff object categorizing chunk changes
        """
        # Build hash lookup for existing chunks
        existing_by_hash: dict[int, Chunk] = {}
        for chunk in existing_chunks:
            if chunk.content_hash is None:
                # Compute hash for existing chunks that don't have one
                content_hash = self.compute_chunk_hash(chunk)
                existing_by_hash[content_hash] = chunk
            else:
                existing_by_hash[chunk.content_hash] = chunk

        # Build hash lookup for new chunks and compute hashes
        new_by_hash: dict[int, Chunk] = {}
        for chunk in new_chunks:
            content_hash = self.compute_chunk_hash(chunk)
            new_by_hash[content_hash] = chunk

        # Find intersections and differences
        existing_hashes = set(existing_by_hash.keys())
        new_hashes = set(new_by_hash.keys())

        unchanged_hashes = existing_hashes & new_hashes
        deleted_hashes = existing_hashes - new_hashes
        added_hashes = new_hashes - existing_hashes

        return ChunkDiff(
            unchanged=[existing_by_hash[h] for h in unchanged_hashes],
            modified=[],  # For now, we consider all changes as add/delete
            added=[new_by_hash[h] for h in added_hashes], 
            deleted=[existing_by_hash[h] for h in deleted_hashes]
        )

    def with_computed_hashes(self, chunks: list[Chunk]) -> list[Chunk]:
        """Return chunks with content_hash field populated.
        
        Args:
            chunks: List of chunks to populate hashes for
            
        Returns:
            List of chunks with content_hash field set
        """
        result = []
        for chunk in chunks:
            if chunk.content_hash is None:
                content_hash = self.compute_chunk_hash(chunk)
                # Create new chunk with hash using the dataclass replace pattern
                new_chunk = Chunk(
                    id=chunk.id,
                    symbol=chunk.symbol,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    code=chunk.code,
                    chunk_type=chunk.chunk_type,
                    file_id=chunk.file_id,
                    language=chunk.language,
                    file_path=chunk.file_path,
                    parent_header=chunk.parent_header,
                    start_byte=chunk.start_byte,
                    end_byte=chunk.end_byte,
                    created_at=chunk.created_at,
                    updated_at=chunk.updated_at,
                    content_hash=content_hash
                )
                result.append(new_chunk)
            else:
                result.append(chunk)
        return result