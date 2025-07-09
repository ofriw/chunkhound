"""Base tree-sitter parser with shared functionality for ChunkHound parsers."""

import time
from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig, ParseResult

try:
    from tree_sitter import Language as TSLanguage
    from tree_sitter import Node as TSNode
    from tree_sitter import Parser as TSParser
    from tree_sitter_language_pack import get_language, get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class TreeSitterParserBase:
    """Base class for tree-sitter parsers with shared functionality."""

    def __init__(self, language: CoreLanguage, config: ParseConfig | None = None):
        """Initialize base tree-sitter parser.

        Args:
            language: Programming language this parser handles
            config: Optional parse configuration
        """
        self._language_name = language
        self._language = None
        self._parser = None
        self._initialized = False
        self._config = config or self._get_default_config()

        # Initialize parser - crash if dependencies unavailable
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                f"{language.value} tree-sitter dependencies not available - install tree-sitter-language-pack"
            )

        if not self._initialize():
            raise RuntimeError(f"Failed to initialize {language.value} parser")

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for this parser. Override in subclasses."""
        return ParseConfig(
            language=self._language_name,
            chunk_types={ChunkType.FUNCTION, ChunkType.CLASS},
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=True,
            include_comments=False,
            include_docstrings=True,
            max_depth=10,
            use_cache=True,
        )

    def _get_tree_sitter_language_name(self) -> str:
        """Get tree-sitter language name. Override in subclasses if different."""
        return self._language_name.value.lower()

    def _initialize(self) -> bool:
        """Initialize the tree-sitter parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not TREE_SITTER_AVAILABLE:
            logger.error(
                f"{self._language_name.value} tree-sitter support not available"
            )
            return False

        try:
            if get_language and get_parser:
                ts_lang_name = self._get_tree_sitter_language_name()
                self._language = get_language(ts_lang_name)
                self._parser = get_parser(ts_lang_name)
                self._initialized = True
                logger.debug(
                    f"{self._language_name.value} parser initialized successfully"
                )
                return True
            else:
                logger.error(
                    f"{self._language_name.value} parser dependencies not available"
                )
                return False
        except Exception as e:
            logger.error(
                f"Failed to initialize {self._language_name.value} parser: {e}"
            )
            return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return self._language_name

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return TREE_SITTER_AVAILABLE and self._initialized

    def parse_file(self, file_path: Path, source: str | None = None) -> ParseResult:
        """Parse a file and extract semantic chunks.

        Args:
            file_path: Path to source file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append(f"{self._language_name.value} parser not available")
            return ParseResult(
                chunks=chunks,
                language=self.language,
                total_chunks=0,
                parse_time=time.time() - start_time,
                errors=errors,
                warnings=warnings,
                metadata={"file_path": str(file_path)},
            )

        try:
            # Read source if not provided
            if source is None:
                with open(file_path, encoding="utf-8") as f:
                    source = f.read()

            # Parse with tree-sitter
            if self._parser is None:
                errors.append(f"{self._language_name.value} parser not initialized")
                return ParseResult(
                    chunks=chunks,
                    language=self.language,
                    total_chunks=0,
                    parse_time=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                    metadata={"file_path": str(file_path)},
                )

            tree = self._parser.parse(bytes(source, "utf8"))

            # Extract semantic units - delegate to subclass
            chunks = self._extract_chunks(tree.root_node, source, file_path)

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")

        except Exception as e:
            error_msg = (
                f"Failed to parse {self._language_name.value} file {file_path}: {e}"
            )
            logger.error(error_msg)
            errors.append(error_msg)

        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={"file_path": str(file_path)},
        )

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from AST. Override in subclasses.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file

        Returns:
            List of extracted chunks
        """
        raise NotImplementedError("Subclasses must implement _extract_chunks")

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte : node.end_byte]

    def _create_chunk(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunk_type: ChunkType,
        name: str,
        display_name: str | None = None,
        parent: str | None = None,
        **extra_fields,
    ) -> dict[str, Any]:
        """Create a standard chunk dictionary.

        Args:
            node: AST node
            source: Source code string
            file_path: Path to source file
            chunk_type: Type of chunk
            name: Chunk name/symbol
            display_name: Display name (defaults to name)
            parent: Parent symbol name
            **extra_fields: Additional fields to include

        Returns:
            Chunk dictionary
        """
        code = self._get_node_text(node, source)

        chunk = {
            "symbol": name,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "code": code,
            "chunk_type": chunk_type.value,
            "language": self._language_name.value.lower(),
            "path": str(file_path),
            "name": name,
            "display_name": display_name or name,
            "content": code,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }

        if parent:
            chunk["parent"] = parent

        # Add extra fields
        chunk.update(extra_fields)

        return chunk

    def _extract_comments_generic(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        comment_patterns: list[str],
    ) -> list[dict[str, Any]]:
        """Extract comments using generic patterns.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file
            comment_patterns: List of tree-sitter query patterns for comments

        Returns:
            List of comment chunks
        """
        chunks = []

        if not comment_patterns or self._language is None:
            return chunks

        try:
            for pattern in comment_patterns:
                query = self._language.query(pattern)
                matches = query.matches(tree_node)

                for match in matches:
                    pattern_index, captures = match

                    for capture_name, nodes in captures.items():
                        for node in nodes:
                            comment_text = self._get_node_text(node, source)

                            # Skip empty comments
                            if not comment_text.strip():
                                continue

                            cleaned_text = self._clean_comment_text(comment_text)
                            symbol = f"comment:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node=node,
                                source=source,
                                file_path=file_path,
                                chunk_type=ChunkType.COMMENT,
                                name=symbol,
                                display_name=f"Comment at line {node.start_point[0] + 1}",
                                content=cleaned_text,
                            )

                            chunks.append(chunk)

        except Exception as e:
            logger.error(
                f"Failed to extract comments for {self._language_name.value}: {e}"
            )

        return chunks

    def _extract_docstrings_generic(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        docstring_patterns: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """Extract docstrings using generic patterns.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file
            docstring_patterns: List of (query_pattern, context_name) tuples

        Returns:
            List of docstring chunks
        """
        chunks = []

        if not docstring_patterns or self._language is None:
            return chunks

        try:
            for pattern, context in docstring_patterns:
                query = self._language.query(pattern)
                matches = query.matches(tree_node)

                for match in matches:
                    pattern_index, captures = match

                    for capture_name, nodes in captures.items():
                        for node in nodes:
                            docstring_text = self._get_node_text(node, source)

                            # Skip empty docstrings
                            if not docstring_text.strip():
                                continue

                            cleaned_text = self._clean_docstring_text(docstring_text)
                            symbol = f"docstring:{context}:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node=node,
                                source=source,
                                file_path=file_path,
                                chunk_type=ChunkType.DOCSTRING,
                                name=symbol,
                                display_name=f"{context.capitalize()} docstring",
                                content=cleaned_text,
                                context=context,
                            )

                            chunks.append(chunk)

        except Exception as e:
            logger.error(
                f"Failed to extract docstrings for {self._language_name.value}: {e}"
            )

        return chunks

    def _clean_comment_text(self, text: str) -> str:
        """Clean comment text by removing comment markers.

        Args:
            text: Raw comment text

        Returns:
            Cleaned comment text
        """
        cleaned = text.strip()

        # Remove common single-line comment markers
        if cleaned.startswith("//"):
            cleaned = cleaned[2:].strip()
        elif cleaned.startswith("#"):
            cleaned = cleaned[1:].strip()
        elif cleaned.startswith("--"):
            cleaned = cleaned[2:].strip()

        # Remove common multi-line comment markers
        if cleaned.startswith("/*") and cleaned.endswith("*/"):
            cleaned = cleaned[2:-2].strip()
        elif cleaned.startswith("<!--") and cleaned.endswith("-->"):
            cleaned = cleaned[4:-3].strip()

        return cleaned

    def _clean_docstring_text(self, text: str) -> str:
        """Clean docstring text by removing quotes.

        Args:
            text: Raw docstring text

        Returns:
            Cleaned docstring text
        """
        cleaned = text.strip()

        # Remove triple quotes
        if cleaned.startswith('"""') and cleaned.endswith('"""'):
            cleaned = cleaned[3:-3]
        elif cleaned.startswith("'''") and cleaned.endswith("'''"):
            cleaned = cleaned[3:-3]
        # Remove single quotes
        elif cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        elif cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]

        return cleaned.strip()
