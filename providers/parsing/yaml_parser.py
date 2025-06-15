"""YAML parser provider implementation for ChunkHound - basic parser for YAML configuration files."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


class YamlParser:
    """YAML parser for configuration and data files."""

    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize YAML parser.

        Args:
            config: Optional parse configuration
        """
        self._initialized = YAML_AVAILABLE

        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.YAML,
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
        return CoreLanguage.YAML

    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return self._initialized and YAML_AVAILABLE

    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a YAML file and extract semantic chunks.

        Args:
            file_path: Path to YAML file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("YAML parser not available - install PyYAML")
            return ParseResult(
                chunks=chunks,
                language=self.language,
                total_chunks=0,
                parse_time=time.time() - start_time,
                errors=errors,
                warnings=warnings,
                metadata={"file_path": str(file_path)}
            )

        try:
            # Read source if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

            # Validate YAML syntax
            try:
                yaml_data = yaml.safe_load(source)
                logger.debug(f"YAML file {file_path} parsed successfully")
            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML syntax: {e}")
                # Still try to create a basic chunk for search
                yaml_data = None

            # Create chunks based on YAML structure
            if yaml_data is not None:
                chunks.extend(self._extract_yaml_chunks(yaml_data, source, file_path))
            else:
                # Create a fallback chunk for invalid YAML
                chunks.append(self._create_fallback_chunk(source, file_path))

            logger.debug(f"Extracted {len(chunks)} chunks from YAML file {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse YAML file {file_path}: {e}"
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

    def _extract_yaml_chunks(self, yaml_data: Any, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract chunks from parsed YAML data."""
        chunks = []

        if isinstance(yaml_data, dict):
            # For dictionaries, create chunks for top-level keys
            for key, value in yaml_data.items():
                chunk = self._create_key_chunk(key, value, source, file_path)
                if chunk:
                    chunks.append(chunk)
        elif isinstance(yaml_data, list):
            # For arrays, create a single chunk
            chunk = self._create_array_chunk(yaml_data, source, file_path)
            if chunk:
                chunks.append(chunk)
        else:
            # For primitive values, create a single chunk
            chunk = self._create_value_chunk(yaml_data, source, file_path)
            if chunk:
                chunks.append(chunk)

        # Always create a full-file chunk for comprehensive search
        full_file_chunk = self._create_full_file_chunk(source, file_path)
        if full_file_chunk:
            chunks.append(full_file_chunk)

        return chunks

    def _create_key_chunk(self, key: str, value: Any, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a YAML key-value pair."""
        try:
            # Create a clean symbol from the key
            symbol = self._sanitize_symbol(key)

            # Create content string
            if isinstance(value, (dict, list)):
                value_str = yaml.dump(value, default_flow_style=False, indent=2)
            else:
                value_str = str(value)

            content = f'{key}: {value_str}'

            # Truncate if too long
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            # Estimate line numbers (simple approximation)
            lines_before = source[:source.find(f'{key}:')].count('\n') if f'{key}:' in source else 0
            lines_in_content = content.count('\n')

            return {
                "symbol": symbol,
                "start_line": lines_before + 1,
                "end_line": lines_before + max(1, lines_in_content) + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "yaml",
                "path": str(file_path),
                "name": key,
                "display_name": f"YAML key: {key}",
                "content": content,
                "start_byte": 0,  # Simplified
                "end_byte": len(content),  # Simplified
                "yaml_key": key,
                "yaml_type": type(value).__name__,
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for YAML key '{key}': {e}")
            return None

    def _create_array_chunk(self, array_data: List[Any], source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a YAML array."""
        try:
            content = yaml.dump(array_data, default_flow_style=False, indent=2)

            # Truncate if too long
            if len(content) > self._config.max_chunk_size:
                content = content[:self._config.max_chunk_size - 3] + "..."

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            lines_in_content = content.count('\n')

            return {
                "symbol": "yaml_array",
                "start_line": 1,
                "end_line": max(1, lines_in_content) + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "yaml",
                "path": str(file_path),
                "name": "yaml_array",
                "display_name": f"YAML array ({len(array_data)} items)",
                "content": content,
                "start_byte": 0,
                "end_byte": len(content),
                "yaml_type": "array",
                "yaml_length": len(array_data),
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for YAML array: {e}")
            return None

    def _create_value_chunk(self, value: Any, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for a simple YAML value."""
        try:
            content = yaml.dump(value, default_flow_style=False) if not isinstance(value, str) else str(value)

            # Skip if too short
            if len(content) < self._config.min_chunk_size:
                return None

            return {
                "symbol": "yaml_value",
                "start_line": 1,
                "end_line": 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "yaml",
                "path": str(file_path),
                "name": "yaml_value",
                "display_name": f"YAML value ({type(value).__name__})",
                "content": content,
                "start_byte": 0,
                "end_byte": len(content),
                "yaml_type": type(value).__name__,
            }
        except Exception as e:
            logger.warning(f"Failed to create chunk for YAML value: {e}")
            return None

    def _create_full_file_chunk(self, source: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Create a chunk for the entire YAML file."""
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
                "symbol": "yaml_file",
                "start_line": 1,
                "end_line": lines_in_content + 1,
                "code": content,
                "chunk_type": ChunkType.BLOCK.value,
                "language": "yaml",
                "path": str(file_path),
                "name": file_path.stem,
                "display_name": f"YAML file: {file_path.name}",
                "content": content,
                "start_byte": 0,
                "end_byte": len(source),
                "yaml_type": "file",
            }
        except Exception as e:
            logger.warning(f"Failed to create full file chunk for YAML: {e}")
            return None

    def _create_fallback_chunk(self, source: str, file_path: Path) -> Dict[str, Any]:
        """Create a fallback chunk for unparseable YAML."""
        content = source[:self._config.max_chunk_size] if len(source) > self._config.max_chunk_size else source
        lines_in_content = content.count('\n')

        return {
            "symbol": "yaml_raw",
            "start_line": 1,
            "end_line": lines_in_content + 1,
            "code": content,
            "chunk_type": ChunkType.BLOCK.value,
            "language": "yaml",
            "path": str(file_path),
            "name": file_path.stem,
            "display_name": f"YAML file (raw): {file_path.name}",
            "content": content,
            "start_byte": 0,
            "end_byte": len(content),
            "yaml_type": "raw",
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
