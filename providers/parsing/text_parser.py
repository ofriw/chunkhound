"""Text parser provider implementation for ChunkHound - basic parser for plain text files."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time
import re

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult


class TextParser:
    """Text parser for plain text and documentation files."""

    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize Text parser.

        Args:
            config: Optional parse configuration
        """
        self._initialized = True

        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.TEXT,
            chunk_types={ChunkType.PARAGRAPH, ChunkType.BLOCK},
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=False,
            include_comments=False,
            include_docstrings=False,
            max_depth=10,
            use_cache=True
        )

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.TEXT

    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return self._initialized

    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a text file and extract semantic chunks.

        Args:
            file_path: Path to text file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        try:
            # Read source if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

            # Create chunks based on text structure
            if ChunkType.PARAGRAPH in self._config.chunk_types:
                chunks.extend(self._extract_paragraphs(source, file_path))

            # Always create a full-file chunk for comprehensive search
            if ChunkType.BLOCK in self._config.chunk_types:
                full_file_chunk = self._create_full_file_chunk(source, file_path)
                if full_file_chunk:
                    chunks.append(full_file_chunk)

            logger.debug(f"Extracted {len(chunks)} chunks from text file {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse text file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            # Create a fallback chunk even on error
            chunks.append(self._create_fallback_chunk(source or "", file_path))

        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={"file_path": str(file_path)}
        )

    def _extract_paragraphs(self, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract paragraphs from text content."""
        chunks = []

        # Split text into paragraphs (separated by double newlines or more)
        paragraphs = re.split(r'\n\s*\n', source)

        current_line = 1
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()

            # Skip empty paragraphs
            if not paragraph:
                continue

            # Skip paragraphs that are too short
            if len(paragraph) < self._config.min_chunk_size:
                current_line += paragraph.count('\n') + 2  # +2 for paragraph separator
                continue

            # Truncate if too long
            content = paragraph
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            # Create symbol from first few words
            words = paragraph.split()[:5]
            symbol = '_'.join(self._sanitize_word(word) for word in words if word)
            if not symbol:
                symbol = f"paragraph_{i + 1}"

            # Create display name from first line or first few words
            first_line = paragraph.split('\n')[0]
            display_name = first_line[:100]
            if len(first_line) > 100:
                display_name += "..."

            lines_in_paragraph = paragraph.count('\n')

            chunk = {
                "symbol": symbol,
                "start_line": current_line,
                "end_line": current_line + lines_in_paragraph,
                "code": content,
                "chunk_type": ChunkType.PARAGRAPH.value,
                "language": "text",
                "path": str(file_path),
                "name": symbol,
                "display_name": display_name,
                "content": content,
                "start_byte": 0,  # Simplified
                "end_byte": len(content),
                "paragraph_index": i + 1,
                "word_count": len(paragraph.split()),
            }

            chunks.append(chunk)
            current_line += lines_in_paragraph + 2  # +2 for paragraph separator

        return chunks

    def _create_full_file_chunk(self, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for the entire text file."""
        try:
            # Skip if too short
            if len(source) < self._config.min_chunk_size:
                return None

            # Truncate if too long
            content = source
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            lines_in_content = source.count('\n')

            # Create display name from first line
            first_line = source.split('\n')[0] if source else ""
            display_name = f"Text file: {file_path.name}"
            if first_line:
                display_name += f" - {first_line[:50]}"
                if len(first_line) > 50:
                    display_name += "..."

            return {
                "symbol": "text_file",
                "start_line": 1,
                "end_line": lines_in_content + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "text",
                "path": str(file_path),
                "name": file_path.stem,
                "display_name": display_name,
                "content": content,
                "start_byte": 0,
                "end_byte": len(source),
                "text_type": "file",
                "line_count": lines_in_content + 1,
                "word_count": len(source.split()),
                "char_count": len(source),
            }
        except Exception as e:
            logger.warning(f"Failed to create full file chunk for text: {e}")
            return None

    def _create_fallback_chunk(self, source: str, file_path: Path) -> Dict[str, Any]:
        """Create a fallback chunk for text files."""
        content = source[:self._config.max_chunk_size] if len(source) > self._config.max_chunk_size else source
        lines_in_content = content.count('\n')

        return {
            "symbol": "text_raw",
            "start_line": 1,
            "end_line": lines_in_content + 1,
            "code": content,
            "chunk_type": ChunkType.BLOCK.value,
            "language": "text",
            "path": str(file_path),
            "name": file_path.stem,
            "display_name": f"Text file (raw): {file_path.name}",
            "content": content,
            "start_byte": 0,
            "end_byte": len(content),
            "text_type": "raw",
        }

    def _sanitize_word(self, word: str) -> str:
        """Sanitize a word for use in symbol names."""
        # Remove punctuation and convert to lowercase
        sanitized = re.sub(r'[^\w]', '', word.lower())
        return sanitized if sanitized else "word"

    def _sanitize_symbol(self, symbol: str) -> str:
        """Sanitize a symbol name for use as identifier."""
        # Replace non-alphanumeric characters with underscores
        sanitized = ''.join(c if c.isalnum() else '_' for c in symbol)

        # Remove leading/trailing underscores and collapse multiple underscores
        sanitized = '_'.join(part for part in sanitized.split('_') if part)

        # Ensure it's not empty
        if not sanitized:
            sanitized = "unknown"

        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]

        return sanitized
