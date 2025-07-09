"""TOML language parser provider implementation for ChunkHound using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

try:
    from tree_sitter import Language, Parser
    from tree_sitter import Node as TSNode
    from tree_sitter_language_pack import get_language, get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    TSNode = None
    Language = None
    Parser = None
    get_language = None
    get_parser = None


class TomlParser(TreeSitterParserBase):
    """TOML configuration file parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize TOML parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.TOML, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for TOML parser."""
        return ParseConfig(
            language=CoreLanguage.TOML,
            chunk_types={
                ChunkType.TABLE,
                ChunkType.KEY_VALUE,
                ChunkType.ARRAY,
                ChunkType.BLOCK,
                ChunkType.COMMENT,
            },
            max_chunk_size=4000,
            min_chunk_size=50,
            include_imports=False,
            include_comments=True,
            include_docstrings=False,
            max_depth=10,
            use_cache=True,
        )

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from TOML AST.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file

        Returns:
            List of extracted chunks
        """
        chunks = []

        if not self.is_available:
            return chunks

        try:
            # Extract different chunk types based on configuration
            if ChunkType.TABLE in self._config.chunk_types:
                chunks.extend(self._extract_tables(tree_node, source, file_path))

            if ChunkType.KEY_VALUE in self._config.chunk_types:
                chunks.extend(self._extract_key_values(tree_node, source, file_path))

            if ChunkType.ARRAY in self._config.chunk_types:
                chunks.extend(self._extract_arrays(tree_node, source, file_path))

            if ChunkType.BLOCK in self._config.chunk_types:
                chunks.extend(self._extract_blocks(tree_node, source, file_path))

            # Extract comments
            if ChunkType.COMMENT in self._config.chunk_types:
                comment_patterns = ["(comment) @comment"]
                chunks.extend(
                    self._extract_comments_generic(
                        tree_node, source, file_path, comment_patterns
                    )
                )

            # Sort chunks by start position
            chunks.sort(
                key=lambda x: (x.get("start_line", 0), x.get("start_column", 0))
            )

            logger.debug(f"Extracted {len(chunks)} chunks from TOML file {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Error extracting chunks from TOML file {file_path}: {e}")
            return []

    def parse_content(
        self, content: str, file_path: Path = None
    ) -> list[dict[str, Any]]:
        """Parse TOML content string and extract semantic chunks.

        Args:
            content: TOML content to parse
            file_path: Optional file path for context

        Returns:
            List of chunk dictionaries
        """
        if not self.is_available:
            return []

        if file_path is None:
            file_path = Path("content.toml")

        try:
            tree = self._parser.parse(bytes(content, "utf8"))
            return self._extract_chunks(tree.root_node, content, file_path)
        except Exception as e:
            logger.error(f"Error parsing TOML content: {e}")
            return []

    def _extract_tables(
        self, node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract table definitions from TOML."""
        tables = []
        source_lines = source.split("\n")

        def extract_table_recursive(current_node: TSNode):
            # Handle array of tables [[table.name]]
            if current_node.type == "table_array_element":
                table_header = None
                table_content_nodes = []

                for child in current_node.children:
                    if child.type == "bare_key":
                        table_header = self._get_node_text(child, source_lines)
                    elif child.type == "pair":
                        table_content_nodes.append(child)

                if table_header:
                    start_line = current_node.start_point[0] + 1
                    end_line = current_node.end_point[0] + 1

                    table_text = self._get_node_text(current_node, source_lines)

                    tables.append(
                        {
                            "symbol": table_header,
                            "chunk_type": ChunkType.TABLE,
                            "start_line": start_line,
                            "end_line": end_line,
                            "code": table_text,
                            "file_path": str(file_path),
                            "language": CoreLanguage.TOML.value,
                            "metadata": {
                                "table_name": table_header,
                                "is_array_table": True,
                                "key_count": len(table_content_nodes),
                            },
                        }
                    )

            # Handle regular tables [table.name] syntax
            if current_node.type == "table":
                table_header = None
                table_content_nodes = []

                for child in current_node.children:
                    if child.type == "dotted_key":
                        table_header = self._get_node_text(child, source_lines)
                    elif child.type == "pair":
                        table_content_nodes.append(child)

                if table_header:
                    start_line = current_node.start_point[0] + 1
                    end_line = current_node.end_point[0] + 1

                    table_text = self._get_node_text(current_node, source_lines)

                    tables.append(
                        {
                            "symbol": table_header,
                            "chunk_type": ChunkType.TABLE,
                            "start_line": start_line,
                            "end_line": end_line,
                            "code": table_text,
                            "file_path": str(file_path),
                            "language": CoreLanguage.TOML.value,
                            "metadata": {
                                "table_name": table_header,
                                "is_array_table": False,
                                "key_count": len(table_content_nodes),
                            },
                        }
                    )

            for child in current_node.children:
                extract_table_recursive(child)

        extract_table_recursive(node)
        return tables

    def _extract_key_values(
        self, node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract key-value pairs from TOML."""
        key_values = []
        source_lines = source.split("\n")

        def extract_kv_recursive(current_node: TSNode, context_path: str = ""):
            if current_node.type == "pair":
                key_node = None
                value_node = None

                for child in current_node.children:
                    if child.type in ["bare_key", "quoted_key", "dotted_key"]:
                        key_node = child
                    elif child.type in [
                        "string",
                        "integer",
                        "float",
                        "boolean",
                        "array",
                        "inline_table",
                    ]:
                        value_node = child

                if key_node:
                    key_name = self._get_node_text(key_node, source_lines)
                    full_key = (
                        f"{context_path}.{key_name}" if context_path else key_name
                    )

                    start_line = current_node.start_point[0] + 1
                    end_line = current_node.end_point[0] + 1

                    kv_text = self._get_node_text(current_node, source_lines)

                    key_values.append(
                        {
                            "symbol": full_key,
                            "chunk_type": ChunkType.KEY_VALUE,
                            "start_line": start_line,
                            "end_line": end_line,
                            "code": kv_text,
                            "file_path": str(file_path),
                            "language": CoreLanguage.TOML.value,
                            "metadata": {
                                "key": key_name,
                                "full_key": full_key,
                                "value_type": value_node.type
                                if value_node
                                else "unknown",
                                "context": context_path,
                            },
                        }
                    )

            # Update context for nested structures
            new_context = context_path
            if current_node.type == "dotted_key":
                new_context = self._get_node_text(current_node, source_lines)
            elif current_node.type == "table" and current_node.children:
                for child in current_node.children:
                    if child.type == "dotted_key":
                        new_context = self._get_node_text(child, source_lines)
                        break

            for child in current_node.children:
                extract_kv_recursive(child, new_context)

        extract_kv_recursive(node)
        return key_values

    def _extract_arrays(
        self, node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract array definitions from TOML."""
        arrays = []
        source_lines = source.split("\n")

        def extract_array_recursive(current_node: TSNode):
            if current_node.type == "array":
                start_line = current_node.start_point[0] + 1
                end_line = current_node.end_point[0] + 1

                array_text = self._get_node_text(current_node, source_lines)

                # Try to find the key this array belongs to
                parent_key = "array"
                if current_node.parent and current_node.parent.type == "pair":
                    for sibling in current_node.parent.children:
                        if sibling.type in ["bare_key", "quoted_key", "dotted_key"]:
                            parent_key = self._get_node_text(sibling, source_lines)
                            break

                arrays.append(
                    {
                        "symbol": parent_key,
                        "chunk_type": ChunkType.ARRAY,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": array_text,
                        "file_path": str(file_path),
                        "language": CoreLanguage.TOML.value,
                        "metadata": {
                            "array_key": parent_key,
                            "element_count": len(
                                [
                                    child
                                    for child in current_node.children
                                    if child.type != ","
                                ]
                            ),
                        },
                    }
                )

            for child in current_node.children:
                extract_array_recursive(child)

        extract_array_recursive(node)
        return arrays

    def _extract_blocks(
        self, node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract generic configuration blocks from TOML."""
        blocks = []
        source_lines = source.split("\n")

        def extract_block_recursive(current_node: TSNode):
            # Consider inline tables as blocks
            if current_node.type == "inline_table":
                start_line = current_node.start_point[0] + 1
                end_line = current_node.end_point[0] + 1

                block_text = self._get_node_text(current_node, source_lines)

                # Find parent key
                parent_key = "inline_table"
                if current_node.parent and current_node.parent.type == "pair":
                    for sibling in current_node.parent.children:
                        if sibling.type in ["bare_key", "quoted_key", "dotted_key"]:
                            parent_key = self._get_node_text(sibling, source_lines)
                            break

                blocks.append(
                    {
                        "symbol": parent_key,
                        "chunk_type": ChunkType.BLOCK,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": block_text,
                        "file_path": str(file_path),
                        "language": CoreLanguage.TOML.value,
                        "metadata": {
                            "block_type": "inline_table",
                            "parent_key": parent_key,
                        },
                    }
                )

            for child in current_node.children:
                extract_block_recursive(child)

        extract_block_recursive(node)
        return blocks

    def _get_node_text(self, node: TSNode, source_lines: list[str]) -> str:
        """Extract text content from a tree-sitter node."""
        start_row, start_col = node.start_point
        end_row, end_col = node.end_point

        if start_row == end_row:
            return source_lines[start_row][start_col:end_col]

        lines = [source_lines[start_row][start_col:]]
        for row in range(start_row + 1, end_row):
            lines.append(source_lines[row])
        lines.append(source_lines[end_row][:end_col])

        return "\n".join(lines)
