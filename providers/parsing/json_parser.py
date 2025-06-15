"""JSON parser provider implementation for ChunkHound - basic parser for JSON configuration files."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import json
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult


class JsonParser:
    """JSON parser for configuration and data files."""

    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize JSON parser.

        Args:
            config: Optional parse configuration
        """
        self._initialized = True

        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.JSON,
            chunk_types={ChunkType.BLOCK},
            max_chunk_size=8000,
            min_chunk_size=50,
            include_imports=False,
            include_comments=False,
            include_docstrings=False,
            max_depth=10,
            use_cache=True
        )

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.JSON

    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return self._initialized

    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a JSON file and extract semantic chunks.

        Args:
            file_path: Path to JSON file
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

            # Validate JSON syntax
            try:
                json_data = json.loads(source)
                logger.debug(f"JSON file {file_path} parsed successfully")
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON syntax: {e}")
                # Still try to create a basic chunk for search
                json_data = None

            # Create chunks based on JSON structure
            if json_data is not None:
                chunks.extend(self._extract_json_chunks(json_data, source, file_path))
            else:
                # Create a fallback chunk for invalid JSON
                chunks.append(self._create_fallback_chunk(source, file_path))

            logger.debug(f"Extracted {len(chunks)} chunks from JSON file {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse JSON file {file_path}: {e}"
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

    def _extract_json_chunks(self, json_data: Any, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract chunks from parsed JSON data."""
        chunks = []

        if isinstance(json_data, dict):
            # For dictionaries, create chunks for top-level keys
            for key, value in json_data.items():
                chunk = self._create_key_chunk(key, value, source, file_path)
                if chunk:
                    chunks.append(chunk)
        elif isinstance(json_data, list):
            # For arrays, create a single chunk
            chunk = self._create_array_chunk(json_data, source, file_path)
            if chunk:
                chunks.append(chunk)
        else:
            # For primitive values, create a single chunk
            chunk = self._create_value_chunk(json_data, source, file_path)
            if chunk:
                chunks.append(chunk)

        # Always create a full-file chunk for comprehensive search
        full_file_chunk = self._create_full_file_chunk(source, file_path)
        if full_file_chunk:
            chunks.append(full_file_chunk)

        return chunks

    def _create_key_chunk(self, key: str, value: Any, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a JSON key-value pair."""
        try:
            # Create a clean symbol from the key
            symbol = self._sanitize_symbol(key)

            # Create content string
            value_str = json.dumps(value, indent=2) if not isinstance(value, str) else str(value)
            content = f'"{key}": {value_str}'

            # Truncate if too long
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            # Estimate line numbers (simple approximation)
            lines_before = source[:source.find(f'"{key}"')].count('\n') if f'"{key}"' in source else 0
            lines_in_content = content.count('\n')

            return {
                "symbol": symbol,
                "start_line": lines_before + 1,
                "end_line": lines_before + max(1, lines_in_content) + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "json",
                "path": str(file_path),
                "name": key,
                "display_name": f"JSON key: {key}",
                "content": content,
                "start_byte": 0,  # Simplified
                "end_byte": len(content),  # Simplified
                "json_key": key,
                "json_type": type(value).__name__,
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for JSON key '{key}': {e}")
            return None

    def _create_array_chunk(self, array_data: List[Any], source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a JSON array."""
        try:
            content = json.dumps(array_data, indent=2)

            # Truncate if too long
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            lines_in_content = content.count('\n')

            return {
                "symbol": "json_array",
                "start_line": 1,
                "end_line": max(1, lines_in_content) + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "json",
                "path": str(file_path),
                "name": "json_array",
                "display_name": f"JSON array ({len(array_data)} items)",
                "content": content,
                "start_byte": 0,
                "end_byte": len(content),
                "json_type": "array",
                "json_length": len(array_data),
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for JSON array: {e}")
            return None

    def _create_value_chunk(self, value: Any, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a simple JSON value."""
        try:
            content = json.dumps(value, indent=2) if not isinstance(value, str) else str(value)

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            return {
                "symbol": "json_value",
                "start_line": 1,
                "end_line": 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "json",
                "path": str(file_path),
                "name": "json_value",
                "display_name": f"JSON value ({type(value).__name__})",
                "content": content,
                "start_byte": 0,
                "end_byte": len(content),
                "json_type": type(value).__name__,
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for JSON value: {e}")
            return None

    def _create_full_file_chunk(self, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for the entire JSON file."""
        try:
            # Skip if too short
            if len(source) < self._config.min_chunk_size:
                return None

            # Truncate if too long
            content = source
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            lines_in_content = source.count('\n')

            return {
                "symbol": "json_file",
                "start_line": 1,
                "end_line": lines_in_content + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "json",
                "path": str(file_path),
                "name": file_path.stem,
                "display_name": f"JSON file: {file_path.name}",
                "content": content,
                "start_byte": 0,
                "end_byte": len(source),
                "json_type": "file",
            }
        except Exception as e:
            logger.warning(f"Failed to create full file chunk for JSON: {e}")
            return None

    def _create_fallback_chunk(self, source: str, file_path: Path) -> Dict[str, Any]:
        """Create a fallback chunk for unparseable JSON."""
        content = source[:self._config.max_chunk_size] if len(source) > self._config.max_chunk_size else source
        lines_in_content = content.count('\n')

        return {
            "symbol": "json_raw",
            "start_line": 1,
            "end_line": lines_in_content + 1,
            "code": content,
            "chunk_type": ChunkType.BLOCK.value,
            "language": "json",
            "path": str(file_path),
            "name": file_path.stem,
            "display_name": f"JSON file (raw): {file_path.name}",
            "content": content,
            "start_byte": 0,
            "end_byte": len(content),
            "json_type": "raw",
        }

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
