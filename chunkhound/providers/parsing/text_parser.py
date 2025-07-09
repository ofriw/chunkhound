"""
Generic text parser for JSON, YAML, and plain text files.

This parser handles structured and unstructured text content that doesn't require
language-specific syntax parsing. It focuses on content extraction and chunking
for search indexing.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from chunkhound.core.types.common import ChunkType, Language


class TextParser:
    """Generic parser for text-based files including JSON, YAML, and plain text."""

    def __init__(self, language: Language):
        """Initialize the text parser for a specific language type.

        Args:
            language: The language type this parser handles (JSON, YAML, or TEXT)
        """
        self._language = language

    @property
    def language(self) -> Language:
        """Programming language this parser handles."""
        return self._language

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return True  # Text parsers are always available

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        if self._language == Language.JSON:
            return {ChunkType.OBJECT, ChunkType.ARRAY, ChunkType.KEY_VALUE}
        elif self._language == Language.YAML:
            return {ChunkType.DOCUMENT, ChunkType.BLOCK, ChunkType.KEY_VALUE}
        else:  # TEXT
            return {ChunkType.BLOCK}

    def parse_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Parse a text-based file and extract searchable chunks.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of chunk dictionaries containing extracted content
        """
        try:
            # Read file content
            with open(file_path, encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                return []

            # Parse based on file type
            if self._language == Language.JSON:
                return self._parse_json(content, file_path)
            elif self._language == Language.YAML:
                return self._parse_yaml(content, file_path)
            else:  # TEXT or fallback
                return self._parse_text(content, file_path)

        except Exception as e:
            # Return a single chunk with the raw content if parsing fails
            return [
                {
                    "symbol": f"file:{file_path.stem}",
                    "start_line": 1,
                    "end_line": 1,
                    "code": content[:1000]
                    if "content" in locals()
                    else f"Error reading file: {e}",
                    "chunk_type": ChunkType.BLOCK,
                    "language": self._language,
                    "file_path": str(file_path),
                }
            ]

    def _parse_json(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """Parse JSON content into searchable chunks."""
        chunks = []

        try:
            # Parse JSON to validate structure
            data = json.loads(content)

            # Create chunks for different JSON sections
            chunks.extend(self._extract_json_chunks(data, file_path))

        except json.JSONDecodeError:
            # If JSON is invalid, treat as raw text
            chunks.append(
                {
                    "symbol": f"file:{file_path.stem}",
                    "start_line": 1,
                    "end_line": len(content.split("\n")),
                    "code": content,
                    "chunk_type": ChunkType.BLOCK,
                    "language": self._language,
                    "file_path": str(file_path),
                }
            )

        return chunks

    def _parse_yaml(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """Parse YAML content into searchable chunks."""
        chunks = []

        try:
            # Parse YAML to validate structure
            data = yaml.safe_load(content)

            # Create chunks for different YAML sections
            chunks.extend(self._extract_yaml_chunks(data, content, file_path))

        except yaml.YAMLError:
            # If YAML is invalid, treat as raw text
            chunks.append(
                {
                    "symbol": f"file:{file_path.stem}",
                    "start_line": 1,
                    "end_line": len(content.split("\n")),
                    "code": content,
                    "chunk_type": ChunkType.BLOCK,
                    "language": self._language,
                    "file_path": str(file_path),
                }
            )

        return chunks

    def _parse_text(self, content: str, file_path: Path) -> list[dict[str, Any]]:
        """Parse plain text content into searchable chunks."""
        chunks = []
        lines = content.split("\n")

        # Split text into logical chunks (paragraphs, sections)
        current_chunk = []
        current_start_line = 1

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Empty line indicates potential chunk boundary
            if not line:
                if current_chunk:
                    chunk_content = "\n".join(current_chunk).strip()
                    if chunk_content:
                        chunks.append(
                            {
                                "symbol": f"text_block_{len(chunks) + 1}",
                                "start_line": current_start_line,
                                "end_line": i - 1,
                                "code": chunk_content,
                                "chunk_type": ChunkType.PARAGRAPH,
                                "language": self._language,
                                "file_path": str(file_path),
                            }
                        )
                    current_chunk = []
                    current_start_line = i + 1
            else:
                current_chunk.append(line)

        # Handle final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk).strip()
            if chunk_content:
                chunks.append(
                    {
                        "symbol": f"text_block_{len(chunks) + 1}",
                        "start_line": current_start_line,
                        "end_line": len(lines),
                        "code": chunk_content,
                        "chunk_type": ChunkType.PARAGRAPH,
                        "language": self._language,
                        "file_path": str(file_path),
                    }
                )

        # If no chunks were created, create one big chunk
        if not chunks:
            chunks.append(
                {
                    "symbol": f"file:{file_path.stem}",
                    "start_line": 1,
                    "end_line": len(lines),
                    "code": content,
                    "chunk_type": ChunkType.BLOCK,
                    "language": self._language,
                    "file_path": str(file_path),
                }
            )

        return chunks

    def _extract_json_chunks(
        self, data: Any, file_path: Path, prefix: str = ""
    ) -> list[dict[str, Any]]:
        """Extract searchable chunks from JSON data structure."""
        chunks = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_prefix = f"{prefix}.{key}" if prefix else key

                # Create chunk for key-value pairs with string values
                if isinstance(value, str) and len(value) > 10:
                    chunks.append(
                        {
                            "symbol": f"json_{current_prefix}",
                            "start_line": 1,  # JSON doesn't have meaningful line numbers
                            "end_line": 1,
                            "code": f"{key}: {value}",
                            "chunk_type": ChunkType.PROPERTY,
                            "language": self._language,
                            "file_path": str(file_path),
                        }
                    )

                # Recursively process nested structures
                elif isinstance(value, (dict, list)):
                    chunks.extend(
                        self._extract_json_chunks(value, file_path, current_prefix)
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
                chunks.extend(
                    self._extract_json_chunks(item, file_path, current_prefix)
                )

        return chunks

    def _extract_yaml_chunks(
        self, data: Any, raw_content: str, file_path: Path, prefix: str = ""
    ) -> list[dict[str, Any]]:
        """Extract searchable chunks from YAML data structure."""
        chunks = []

        # Try to preserve YAML structure by parsing sections
        sections = self._split_yaml_sections(raw_content)

        for i, section in enumerate(sections):
            if section.strip():
                chunks.append(
                    {
                        "symbol": f"yaml_section_{i + 1}",
                        "start_line": 1,  # YAML line tracking is complex
                        "end_line": len(section.split("\n")),
                        "code": section.strip(),
                        "chunk_type": ChunkType.BLOCK,
                        "language": self._language,
                        "file_path": str(file_path),
                    }
                )

        # If no sections found, create chunks from data structure
        if not chunks:
            chunks.extend(self._extract_yaml_data_chunks(data, file_path))

        return chunks

    def _split_yaml_sections(self, content: str) -> list[str]:
        """Split YAML content into logical sections based on top-level keys."""
        sections = []
        current_section = []
        indent_level = 0

        for line in content.split("\n"):
            # Detect top-level keys (no indentation, ends with colon)
            if (
                line
                and not line.startswith(" ")
                and not line.startswith("\t")
                and ":" in line
            ):
                # Save previous section
                if current_section:
                    sections.append("\n".join(current_section))
                    current_section = []

            current_section.append(line)

        # Add final section
        if current_section:
            sections.append("\n".join(current_section))

        return sections

    def _extract_yaml_data_chunks(
        self, data: Any, file_path: Path, prefix: str = ""
    ) -> list[dict[str, Any]]:
        """Extract chunks from YAML data structure when section splitting fails."""
        chunks = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_prefix = f"{prefix}.{key}" if prefix else key

                if isinstance(value, str) and len(value) > 10:
                    chunks.append(
                        {
                            "symbol": f"yaml_{current_prefix}",
                            "start_line": 1,
                            "end_line": 1,
                            "code": f"{key}: {value}",
                            "chunk_type": ChunkType.PROPERTY,
                            "language": self._language,
                            "file_path": str(file_path),
                        }
                    )
                elif isinstance(value, (dict, list)):
                    chunks.extend(
                        self._extract_yaml_data_chunks(value, file_path, current_prefix)
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
                chunks.extend(
                    self._extract_yaml_data_chunks(item, file_path, current_prefix)
                )

        return chunks


# Factory functions for different text-based languages
class JsonParser(TextParser):
    """JSON-specific parser implementation."""

    def __init__(self):
        super().__init__(Language.JSON)

    @property
    def language(self) -> Language:
        return Language.JSON


class YamlParser(TextParser):
    """YAML-specific parser implementation."""

    def __init__(self):
        super().__init__(Language.YAML)

    @property
    def language(self) -> Language:
        return Language.YAML


class PlainTextParser(TextParser):
    """Plain text parser implementation."""

    def __init__(self):
        super().__init__(Language.TEXT)

    @property
    def language(self) -> Language:
        return Language.TEXT
