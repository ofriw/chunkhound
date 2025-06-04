"""Chunker module for ChunkHound - extracts semantic code units from parsed AST."""

from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger


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
            chunk = self._create_chunk(
                symbol=item["symbol"],
                start_line=item["start_line"],
                end_line=item["end_line"],
                code=item["code"],
                chunk_type=item["chunk_type"],
                file_path=file_path
            )
            chunks.append(chunk)
        
        # Filter chunks based on quality criteria
        filtered_chunks = self._filter_chunks(chunks)
        
        logger.debug(f"Created {len(filtered_chunks)} chunks from {file_path}")
        return filtered_chunks
        
    def _create_chunk(self, symbol: str, start_line: int, end_line: int, 
                     code: str, chunk_type: str, file_path: Path) -> Dict[str, Any]:
        """Create a standardized chunk object.
        
        Args:
            symbol: Function or class name
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed) 
            code: Raw code text
            chunk_type: Type of chunk (function, method, class)
            file_path: Source file path
            
        Returns:
            Standardized chunk dictionary
        """
        self.chunk_id_counter += 1
        line_count = end_line - start_line + 1
        
        # Clean up the code - remove excessive whitespace
        cleaned_code = self._clean_code(code)
        
        return {
            "id": self.chunk_id_counter,
            "symbol": symbol,
            "start_line": start_line,
            "end_line": end_line,
            "code": cleaned_code,
            "chunk_type": chunk_type,
            "file_path": str(file_path),
            "line_count": line_count,
            "char_count": len(cleaned_code),
            "relative_path": str(file_path.relative_to(Path.cwd())) if file_path.is_absolute() else str(file_path),
        }
        
    def _filter_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter chunks based on size and quality criteria.
        
        Args:
            chunks: Raw chunks to filter
            
        Returns:
            Filtered chunks meeting quality criteria
        """
        filtered_chunks = []
        
        for chunk in chunks:
            # Size filtering
            if chunk["line_count"] < self.min_chunk_lines:
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