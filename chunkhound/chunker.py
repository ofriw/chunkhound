"""Chunker module for ChunkHound - extracts semantic code units from parsed AST."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from loguru import logger

# Core domain models
from core.models import Chunk
from core.types import ChunkType, Language


class Chunker:
    """Chunker for extracting semantic units from parsed code."""
    
    def __init__(self):
        """Initialize the chunker."""
        self.chunk_id_counter = 0
        self.min_chunk_lines = 3  # Minimum lines for a chunk to be considered
        self.max_chunk_lines = 500  # Maximum lines for a chunk
        
    def chunk_file(self, file_path: Path, parsed_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert parsed AST data into semantic chunks.
        
        Args:
            file_path: Path to the source file
            parsed_data: Parsed AST data from CodeParser
            
        Returns:
            List of semantic chunks with metadata
        """
        logger.debug(f"Chunking file: {file_path} with {len(parsed_data)} parsed items")
        
        if not parsed_data:
            logger.debug(f"No parsed data for {file_path}")
            return []
        
        # Process each parsed item into standardized chunks
        chunks = []
        for item in parsed_data:
            # Extract language info from both old and new formats
            language_info = item.get("language_info") or item.get("language")
            
            chunk = self._create_chunk(
                symbol=item.get("name", item.get("symbol", "unknown")),
                start_line=item["start_line"],
                end_line=item["end_line"],
                code=item.get("content", item.get("code", "")),
                chunk_type=item.get("type", item.get("chunk_type", "unknown")),
                file_path=file_path,
                language_info=language_info
            )
            chunks.append(chunk)
        
        # Filter chunks based on quality criteria
        filtered_chunks = self._filter_chunks(chunks)
        
        logger.debug(f"Created {len(filtered_chunks)} chunks from {file_path}")
        return filtered_chunks
        
    def _create_chunk(self, symbol: str, start_line: int, end_line: int, 
                     code: str, chunk_type: str, file_path: Path, 
                     language_info: Optional[str] = None) -> Dict[str, Any]:
        """Create a standardized chunk object.
        
        Args:
            symbol: Function or class name
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed) 
            code: Raw code text
            chunk_type: Type of chunk (function, method, class, etc.)
            file_path: Source file path
            language_info: Language information for the chunk
            
        Returns:
            Standardized chunk dictionary (backward compatible)
        """
        self.chunk_id_counter += 1
        line_count = end_line - start_line + 1
        
        # Clean up the code - remove excessive whitespace
        cleaned_code = self._clean_code(code)
        
        chunk = {
            "id": self.chunk_id_counter,
            "symbol": symbol,
            "start_line": start_line,
            "end_line": end_line,
            "code": cleaned_code,
            "chunk_type": chunk_type,
            "file_path": str(file_path),
            "line_count": line_count,
            "char_count": len(cleaned_code),
            "relative_path": self._get_relative_path(file_path),
        }
        
        # Add language_info if provided
        if language_info:
            chunk["language_info"] = language_info
            
        return chunk
        
    def _filter_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter chunks based on size and quality criteria.
        
        Args:
            chunks: Raw chunks to filter
            
        Returns:
            Filtered chunks meeting quality criteria
        """
        filtered_chunks = []
        
        for chunk in chunks:
            # Size filtering - different rules for markdown content
            chunk_type = chunk.get("chunk_type", "")
            is_markdown = chunk_type in ["header_1", "header_2", "header_3", "header_4", "header_5", "header_6", "paragraph"]
            
            # For markdown, allow smaller chunks (headers can be 1 line)
            min_lines = 1 if is_markdown else self.min_chunk_lines
            
            if chunk["line_count"] < min_lines:
                logger.debug(f"Skipping chunk {chunk['symbol']}: too small ({chunk['line_count']} lines)")
                continue
                
            if chunk["line_count"] > self.max_chunk_lines:
                logger.debug(f"Skipping chunk {chunk['symbol']}: too large ({chunk['line_count']} lines)")
                continue
            
            # Skip empty or whitespace-only chunks
            if not chunk["code"].strip():
                logger.debug(f"Skipping chunk {chunk['symbol']}: empty or whitespace only")
                continue
            
            # Skip generated code patterns (basic heuristics)
            if self._is_generated_code(chunk["code"]):
                logger.debug(f"Skipping chunk {chunk['symbol']}: appears to be generated")
                continue
            
            filtered_chunks.append(chunk)
        
        # Remove duplicates based on symbol and code content
        unique_chunks = self._remove_duplicates(filtered_chunks)
        
        logger.debug(f"Filtered {len(chunks)} chunks to {len(unique_chunks)} unique chunks")
        return unique_chunks
    
    def _get_relative_path(self, file_path: Path) -> str:
        """Get relative path safely, handling files outside working directory."""
        try:
            if file_path.is_absolute():
                return str(file_path.relative_to(Path.cwd()))
            else:
                return str(file_path)
        except ValueError:
            # File is outside current working directory, just use the filename
            return file_path.name
    
    def _clean_code(self, code: str) -> str:
        """Clean up code by removing excessive whitespace while preserving structure."""
        if not code:
            return ""
        
        lines = code.split('\n')
        
        # Remove trailing whitespace from each line
        cleaned_lines = [line.rstrip() for line in lines]
        
        # Remove completely empty lines at the beginning and end
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    def _is_generated_code(self, code: str) -> bool:
        """Check if code appears to be generated using basic heuristics."""
        if not code:
            return True
        
        # Check for common generated code patterns
        generated_patterns = [
            "# Generated by",
            "# Auto-generated",
            "# This file was automatically generated",
            "# DO NOT EDIT",
            "# Automatically created",
        ]
        
        code_lower = code.lower()
        for pattern in generated_patterns:
            if pattern.lower() in code_lower:
                return True
        
        return False
    
    def _remove_duplicates(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate chunks based on symbol and code content."""
        seen = set()
        unique_chunks = []
        
        for chunk in chunks:
            # Create a unique key based on symbol and a hash of the code
            key = (chunk["symbol"], hash(chunk["code"]))
            
            if key not in seen:
                seen.add(key)
                unique_chunks.append(chunk)
            else:
                logger.debug(f"Removing duplicate chunk: {chunk['symbol']}")
        
        return unique_chunks


@dataclass
class ChunkDiff:
    """Represents the difference between old and new chunks for incremental updates."""
    chunks_to_delete: List[int]      # Chunk IDs to remove from database
    chunks_to_insert: List[Dict[str, Any]]  # New chunks to add to database
    chunks_to_update: List[Dict[str, Any]]  # Modified chunks to update in database
    unchanged_count: int             # Number of chunks preserved (for stats)


class IncrementalChunker:
    """Chunker that processes only modified regions for efficient incremental updates."""
    
    def __init__(self):
        """Initialize the incremental chunker."""
        self.base_chunker = Chunker()
        
    def chunk_file_differential(self, 
                               file_path: Path, 
                               old_chunks: List[Dict[str, Any]], 
                               changed_ranges: List[Dict[str, Any]], 
                               new_parsed_data: List[Dict[str, Any]]) -> ChunkDiff:
        """Generate minimal chunk changes by comparing old chunks with new parsed data.
        
        Args:
            file_path: Path to the source file
            old_chunks: Previously stored chunks for this file
            changed_ranges: List of changed regions from CodeParser.get_changed_regions()
            new_parsed_data: New parsed AST data from CodeParser
            
        Returns:
            ChunkDiff containing minimal set of database operations needed
        """
        logger.debug(f"Computing differential chunks for {file_path}")
        logger.debug(f"Old chunks: {len(old_chunks)}, Changed ranges: {len(changed_ranges)}")
        
        # If no changed ranges, nothing to update
        if not changed_ranges:
            logger.debug("No changed ranges detected, preserving all chunks")
            return ChunkDiff(
                chunks_to_delete=[],
                chunks_to_insert=[],
                chunks_to_update=[],
                unchanged_count=len(old_chunks)
            )
        
        # Generate new chunks from the complete parsed data
        new_chunks = self.base_chunker.chunk_file(file_path, new_parsed_data)
        logger.debug(f"Generated {len(new_chunks)} new chunks from parsed data")
        
        # If we have a full file change or structural change, replace everything
        has_structural_change = any(
            change.get('type') in ['full_change', 'structural_change'] 
            for change in changed_ranges
        )
        
        if has_structural_change:
            logger.debug("Structural change detected, replacing all chunks")
            old_chunk_ids = [chunk.get('id') for chunk in old_chunks if chunk.get('id')]
            return ChunkDiff(
                chunks_to_delete=old_chunk_ids,
                chunks_to_insert=new_chunks,
                chunks_to_update=[],
                unchanged_count=0
            )
        
        # Identify which old chunks are affected by the changes
        affected_chunk_ids = self.identify_affected_chunks(old_chunks, changed_ranges)
        logger.debug(f"Identified {len(affected_chunk_ids)} affected chunks")
        
        # Find new chunks that overlap with affected regions
        affected_new_chunks = self.identify_new_chunks_in_ranges(new_chunks, changed_ranges)
        logger.debug(f"Found {len(affected_new_chunks)} new chunks in changed ranges")
        
        # Build the diff
        chunks_to_delete = list(affected_chunk_ids)
        chunks_to_insert = affected_new_chunks
        unchanged_count = len(old_chunks) - len(affected_chunk_ids)
        
        return ChunkDiff(
            chunks_to_delete=chunks_to_delete,
            chunks_to_insert=chunks_to_insert,
            chunks_to_update=[],  # For now, we delete+insert rather than update
            unchanged_count=unchanged_count
        )
    
    def identify_affected_chunks(self, 
                                old_chunks: List[Dict[str, Any]], 
                                changed_ranges: List[Dict[str, Any]]) -> Set[int]:
        """Find chunks that overlap with changed regions and need updating.
        
        Args:
            old_chunks: Previously stored chunks
            changed_ranges: List of changed byte/line ranges
            
        Returns:
            Set of chunk IDs that need to be removed/updated
        """
        affected_ids = set()
        
        for chunk in old_chunks:
            chunk_id = chunk.get('id')
            if not chunk_id:
                continue
                
            chunk_start = chunk.get('start_line', 0)
            chunk_end = chunk.get('end_line', 0)
            
            # Check if chunk overlaps with any changed range
            for change in changed_ranges:
                # Convert byte positions to approximate line positions
                # This is a simplified approach - in production we'd want more precise mapping
                change_start_byte = change.get('start_byte', 0)
                change_end_byte = change.get('end_byte', float('inf'))
                
                # Simple heuristic: assume ~50 chars per line for byte-to-line conversion
                # This is rough but works for detecting overlaps
                change_start_line = max(1, change_start_byte // 50)
                change_end_line = change_end_byte // 50 if change_end_byte != float('inf') else float('inf')
                
                # Check for overlap: chunk intersects with changed range
                if (chunk_start <= change_end_line and chunk_end >= change_start_line):
                    affected_ids.add(chunk_id)
                    logger.debug(f"Chunk {chunk_id} ({chunk_start}-{chunk_end}) overlaps with change ({change_start_line}-{change_end_line})")
                    break
        
        return affected_ids
    
    def identify_new_chunks_in_ranges(self, 
                                     new_chunks: List[Dict[str, Any]], 
                                     changed_ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find new chunks that fall within changed regions.
        
        Args:
            new_chunks: Newly generated chunks
            changed_ranges: List of changed byte/line ranges
            
        Returns:
            List of new chunks that should be inserted
        """
        chunks_in_ranges = []
        
        for chunk in new_chunks:
            chunk_start = chunk.get('start_line', 0)
            chunk_end = chunk.get('end_line', 0)
            
            # Check if chunk falls within any changed range
            for change in changed_ranges:
                # Convert byte positions to approximate line positions
                change_start_byte = change.get('start_byte', 0)
                change_end_byte = change.get('end_byte', float('inf'))
                
                change_start_line = max(1, change_start_byte // 50)
                change_end_line = change_end_byte // 50 if change_end_byte != float('inf') else float('inf')
                
                # Check if chunk overlaps with changed range
                if (chunk_start <= change_end_line and chunk_end >= change_start_line):
                    chunks_in_ranges.append(chunk)
                    logger.debug(f"New chunk '{chunk.get('symbol', 'unknown')}' ({chunk_start}-{chunk_end}) falls in changed range")
                    break
        
        return chunks_in_ranges