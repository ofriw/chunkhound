"""Kotlin language parser provider implementation for ChunkHound using tree-sitter."""

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

    KOTLIN_AVAILABLE = True
except ImportError:
    KOTLIN_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None

# Try direct import as fallback
try:
    import tree_sitter_kotlin as ts_kotlin

    KOTLIN_DIRECT_AVAILABLE = True
except ImportError:
    KOTLIN_DIRECT_AVAILABLE = False
    ts_kotlin = None


class KotlinParser:
    """Kotlin language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Kotlin parser.

        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False

        # Default configuration for Kotlin-specific chunk types
        self._config = config or ParseConfig(
            language=CoreLanguage.KOTLIN,
            chunk_types={
                ChunkType.CLASS,
                ChunkType.INTERFACE,
                ChunkType.METHOD,
                ChunkType.FUNCTION,
                ChunkType.VARIABLE,
                ChunkType.ENUM,
                ChunkType.COMMENT,
                ChunkType.DOCSTRING,
            },
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=True,
            include_comments=False,
            include_docstrings=True,
            max_depth=10,
            use_cache=True,
        )

        # Initialize parser - crash if dependencies unavailable
        if not KOTLIN_AVAILABLE and not KOTLIN_DIRECT_AVAILABLE:
            raise ImportError(
                "Kotlin tree-sitter dependencies not available - install tree-sitter-language-pack or tree-sitter-kotlin"
            )

        if not self._initialize():
            raise RuntimeError("Failed to initialize Kotlin parser")

    def _initialize(self) -> bool:
        """Initialize the Kotlin parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not KOTLIN_AVAILABLE and not KOTLIN_DIRECT_AVAILABLE:
            logger.error("Kotlin tree-sitter support not available")
            return False

        # Try direct import first
        try:
            if KOTLIN_DIRECT_AVAILABLE and ts_kotlin and TSLanguage and TSParser:
                self._language = TSLanguage(ts_kotlin.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Kotlin parser initialized successfully (direct)")
                return True
        except Exception as e:
            logger.debug(f"Direct Kotlin parser initialization failed: {e}")

        # Fallback to language pack
        try:
            if KOTLIN_AVAILABLE and get_language and get_parser:
                self._language = get_language("kotlin")
                self._parser = get_parser("kotlin")
                self._initialized = True
                logger.debug("Kotlin parser initialized successfully (language pack)")
                return True
        except Exception as e:
            logger.error(f"Kotlin parser language pack initialization failed: {e}")

        logger.error("Kotlin parser initialization failed with both methods")
        return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.KOTLIN

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return (KOTLIN_AVAILABLE or KOTLIN_DIRECT_AVAILABLE) and self._initialized

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte : node.end_byte]

    def parse_file(self, file_path: Path, source: str | None = None) -> ParseResult:
        """Parse a Kotlin file and extract semantic chunks.

        Args:
            file_path: Path to Kotlin file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("Kotlin parser not available")
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
                errors.append("Kotlin parser not initialized")
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

            # Extract semantic units
            chunks = self._extract_chunks(tree.root_node, source, file_path)

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse Kotlin file {file_path}: {e}"
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
        """Extract semantic chunks from Kotlin AST.

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
            package_name = self._extract_package(tree_node, source)

            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(
                    self._extract_classes(tree_node, source, file_path, package_name)
                )

            if ChunkType.DATA_CLASS in self._config.chunk_types:
                chunks.extend(
                    self._extract_data_classes(
                        tree_node, source, file_path, package_name
                    )
                )

            if ChunkType.OBJECT in self._config.chunk_types:
                chunks.extend(
                    self._extract_objects(tree_node, source, file_path, package_name)
                )

            if ChunkType.COMPANION_OBJECT in self._config.chunk_types:
                chunks.extend(
                    self._extract_companion_objects(
                        tree_node, source, file_path, package_name
                    )
                )

            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(
                    self._extract_interfaces(tree_node, source, file_path, package_name)
                )

            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(
                    self._extract_enums(tree_node, source, file_path, package_name)
                )

            if (
                ChunkType.METHOD in self._config.chunk_types
                or ChunkType.CONSTRUCTOR in self._config.chunk_types
                or ChunkType.EXTENSION_FUNCTION in self._config.chunk_types
            ):
                chunks.extend(
                    self._extract_methods(tree_node, source, file_path, package_name)
                )

            if ChunkType.FIELD in self._config.chunk_types:
                chunks.extend(
                    self._extract_properties(tree_node, source, file_path, package_name)
                )

            # Extract comments and docstrings
            if ChunkType.COMMENT in self._config.chunk_types:
                chunks.extend(self._extract_comments(tree_node, source, file_path))

            if ChunkType.DOCSTRING in self._config.chunk_types:
                chunks.extend(self._extract_docstrings(tree_node, source, file_path))

        except Exception as e:
            logger.error(f"Failed to extract Kotlin chunks: {e}")

        return chunks

    def _extract_package(self, tree_node: TSNode, source: str) -> str:
        """Extract package name from Kotlin file."""
        try:
            if self._language is None:
                return ""

            query = self._language.query("""
                (package_header) @package_def
            """)

            matches = query.matches(tree_node)

            if not matches:
                return ""

            for pattern_index, captures in matches:
                if "package_def" in captures:
                    package_node = captures["package_def"][0]
                    # Extract package name from the full header text
                    package_text = self._get_node_text(package_node, source)
                    # Simple extraction: remove "package " prefix
                    if package_text.startswith("package "):
                        return package_text[8:].strip()
                    return package_text

            return ""
        except Exception as e:
            logger.error(f"Failed to extract Kotlin package: {e}")
            return ""

    def _extract_classes(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin class definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration) @class_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "class_def" not in captures:
                    continue

                class_node = captures["class_def"][0]

                # Extract class name from the node children
                class_name = "UnnamedClass"
                for child in class_node.children:
                    if child.type in [
                        "simple_identifier",
                        "type_identifier",
                        "identifier",
                    ]:
                        class_name = self._get_node_text(child, source)
                        break

                qualified_name = class_name
                if package_name:
                    qualified_name = f"{package_name}.{class_name}"

                chunk = self._create_chunk(
                    class_node,
                    source,
                    file_path,
                    ChunkType.CLASS,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin classes: {e}")

        return chunks

    def _extract_data_classes(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin data class definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration
                    (modifiers
                        (class_modifier "data")
                    )
                    name: (simple_identifier) @data_class_name
                ) @data_class_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if (
                    "data_class_def" not in captures
                    or "data_class_name" not in captures
                ):
                    continue

                data_class_node = captures["data_class_def"][0]
                data_class_name_node = captures["data_class_name"][0]
                data_class_name = self._get_node_text(data_class_name_node, source)

                qualified_name = data_class_name
                if package_name:
                    qualified_name = f"{package_name}.{data_class_name}"

                chunk = self._create_chunk(
                    data_class_node,
                    source,
                    file_path,
                    ChunkType.DATA_CLASS,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin data classes: {e}")

        return chunks

    def _extract_objects(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin object declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (object_declaration
                    name: (simple_identifier) @object_name
                ) @object_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "object_def" not in captures or "object_name" not in captures:
                    continue

                object_node = captures["object_def"][0]
                object_name_node = captures["object_name"][0]
                object_name = self._get_node_text(object_name_node, source)

                qualified_name = object_name
                if package_name:
                    qualified_name = f"{package_name}.{object_name}"

                chunk = self._create_chunk(
                    object_node,
                    source,
                    file_path,
                    ChunkType.OBJECT,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin objects: {e}")

        return chunks

    def _extract_companion_objects(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin companion object declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (companion_object
                    name: (simple_identifier)? @companion_name
                ) @companion_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "companion_def" not in captures:
                    continue

                companion_node = captures["companion_def"][0]

                # Companion objects may or may not have explicit names
                companion_name = "Companion"
                if "companion_name" in captures:
                    companion_name_node = captures["companion_name"][0]
                    companion_name = self._get_node_text(companion_name_node, source)

                # Find containing class
                parent_class = self._find_containing_class(companion_node, source)

                qualified_name = companion_name
                if parent_class and package_name:
                    qualified_name = f"{package_name}.{parent_class}.{companion_name}"
                elif parent_class:
                    qualified_name = f"{parent_class}.{companion_name}"

                chunk = self._create_chunk(
                    companion_node,
                    source,
                    file_path,
                    ChunkType.COMPANION_OBJECT,
                    qualified_name,
                    companion_name,
                    parent=parent_class if parent_class else None,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin companion objects: {e}")

        return chunks

    def _extract_interfaces(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin interface definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration) @interface_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "interface_def" not in captures:
                    continue

                interface_node = captures["interface_def"][0]

                # Check if this is actually an interface by looking for "interface" keyword
                interface_text = self._get_node_text(interface_node, source)
                if not interface_text.strip().startswith("interface "):
                    continue

                # Extract interface name
                interface_name = "UnnamedInterface"
                for child in interface_node.children:
                    if child.type in [
                        "simple_identifier",
                        "type_identifier",
                        "identifier",
                    ]:
                        interface_name = self._get_node_text(child, source)
                        break

                qualified_name = interface_name
                if package_name:
                    qualified_name = f"{package_name}.{interface_name}"

                chunk = self._create_chunk(
                    interface_node,
                    source,
                    file_path,
                    ChunkType.INTERFACE,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin interfaces: {e}")

        return chunks

    def _extract_enums(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin enum definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration) @enum_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "enum_def" not in captures:
                    continue

                enum_node = captures["enum_def"][0]

                # Check if this is actually an enum class by looking for "enum class" keywords
                enum_text = self._get_node_text(enum_node, source)
                if "enum class" not in enum_text.strip()[:20]:  # Check first 20 chars
                    continue

                # Extract enum name
                enum_name = "UnnamedEnum"
                for child in enum_node.children:
                    if child.type in [
                        "simple_identifier",
                        "type_identifier",
                        "identifier",
                    ]:
                        enum_name = self._get_node_text(child, source)
                        break

                qualified_name = enum_name
                if package_name:
                    qualified_name = f"{package_name}.{enum_name}"

                chunk = self._create_chunk(
                    enum_node,
                    source,
                    file_path,
                    ChunkType.ENUM,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin enums: {e}")

        return chunks

    def _extract_methods(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (function_declaration) @function_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "function_def" not in captures:
                    continue

                function_node = captures["function_def"][0]

                # Extract function name from the node children
                function_name = "unnamed_function"
                for child in function_node.children:
                    if child.type in ["simple_identifier", "identifier"]:
                        function_name = self._get_node_text(child, source)
                        break

                # Check if we want this chunk type
                if ChunkType.FUNCTION not in self._config.chunk_types:
                    continue

                # Find containing class/object
                parent_class = self._find_containing_class(function_node, source)

                # Build qualified name
                if parent_class and package_name:
                    qualified_name = f"{package_name}.{parent_class}.{function_name}"
                elif parent_class:
                    qualified_name = f"{parent_class}.{function_name}"
                else:
                    qualified_name = function_name

                chunk_type = ChunkType.FUNCTION

                chunk = self._create_chunk(
                    function_node,
                    source,
                    file_path,
                    chunk_type,
                    qualified_name,
                    qualified_name,
                    parent=parent_class if parent_class else None,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin methods: {e}")

        return chunks

    def _extract_properties(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Kotlin property definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (property_declaration
                    (variable_declaration
                        (simple_identifier) @property_name
                    )
                ) @property_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "property_def" not in captures or "property_name" not in captures:
                    continue

                property_node = captures["property_def"][0]
                property_name_node = captures["property_name"][0]
                property_name = self._get_node_text(property_name_node, source)

                # Find containing class
                parent_class = self._find_containing_class(property_node, source)

                # Build qualified name
                if parent_class and package_name:
                    qualified_name = f"{package_name}.{parent_class}.{property_name}"
                elif parent_class:
                    qualified_name = f"{parent_class}.{property_name}"
                else:
                    qualified_name = property_name

                chunk = self._create_chunk(
                    property_node,
                    source,
                    file_path,
                    ChunkType.FIELD,
                    qualified_name,
                    property_name,
                    parent=parent_class if parent_class else None,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Kotlin properties: {e}")

        return chunks

    def _find_containing_class(self, node: TSNode, source: str) -> str | None:
        """Find the name of the class containing the given node."""
        current = node.parent

        while current:
            if current.type in ["class_declaration", "object_declaration"]:
                # Find the class/object name
                for i in range(current.child_count):
                    child = current.child(i)
                    if child and child.type in ["simple_identifier", "type_identifier"]:
                        return self._get_node_text(child, source)
            current = current.parent

        return None

    def _create_chunk(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunk_type: ChunkType,
        symbol: str,
        display_name: str,
        parent: str = None,
    ) -> dict[str, Any]:
        """Create a chunk dictionary from a tree-sitter node.

        Args:
            node: Tree-sitter node
            source: Source code string
            file_path: Path to source file
            chunk_type: Type of chunk
            symbol: Symbol name
            display_name: Display name for the chunk
            parent: Optional parent class/object name

        Returns:
            Chunk dictionary
        """
        content = self._get_node_text(node, source)

        chunk = {
            "symbol": symbol,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "code": content,
            "chunk_type": chunk_type.value,
            "language": "kotlin",
            "path": str(file_path),
            "name": symbol,
            "display_name": display_name,
            "content": content,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }

        if parent:
            chunk["parent"] = parent

        return chunk

    def _extract_comments(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Kotlin comments (// and /* */)."""
        # Kotlin tree-sitter may not support these comment node types
        try:
            comment_patterns = ["(line_comment) @comment"]
            return self._extract_comments_generic(
                tree_node, source, file_path, comment_patterns
            )
        except Exception:
            return []

    def _extract_docstrings(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Kotlin KDoc comments (/** */)."""
        chunks = []

        if self._language is None:
            return chunks

        try:
            # Kotlin tree-sitter may not support multiline_comment queries
            query = self._language.query("(multiline_comment) @comment")
            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                for capture_name, nodes in captures.items():
                    for node in nodes:
                        comment_text = self._get_node_text(node, source)

                        # Check if it's a KDoc comment (starts with /**)
                        if comment_text.strip().startswith("/**"):
                            cleaned_text = self._clean_kdoc_text(comment_text)
                            symbol = f"kdoc:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node,
                                source,
                                file_path,
                                ChunkType.DOCSTRING,
                                symbol,
                                f"KDoc at line {node.start_point[0] + 1}",
                            )
                            chunk["content"] = cleaned_text

                            chunks.append(chunk)

        except Exception:
            # Silently fail if queries not supported
            pass

        return chunks

    def _clean_kdoc_text(self, text: str) -> str:
        """Clean KDoc text by removing /** */ markers and * prefixes."""
        cleaned = text.strip()

        # Remove /** */ markers
        if cleaned.startswith("/**") and cleaned.endswith("*/"):
            cleaned = cleaned[3:-2]

        # Remove leading * from each line
        lines = cleaned.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].lstrip()
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _extract_comments_generic(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        comment_patterns: list[str],
    ) -> list[dict[str, Any]]:
        """Extract comments using generic patterns."""
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

                            # Skip empty comments and KDoc comments (handled separately)
                            if (
                                not comment_text.strip()
                                or comment_text.strip().startswith("/**")
                            ):
                                continue

                            cleaned_text = self._clean_comment_text(comment_text)
                            symbol = f"comment:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node,
                                source,
                                file_path,
                                ChunkType.COMMENT,
                                symbol,
                                f"Comment at line {node.start_point[0] + 1}",
                            )
                            chunk["content"] = cleaned_text

                            chunks.append(chunk)

        except Exception:
            # Silently fail if queries not supported
            pass

        return chunks

    def _clean_comment_text(self, text: str) -> str:
        """Clean comment text by removing comment markers."""
        cleaned = text.strip()

        # Remove common single-line comment markers
        if cleaned.startswith("//"):
            cleaned = cleaned[2:].strip()

        # Remove common multi-line comment markers (but not KDoc)
        if (
            cleaned.startswith("/*")
            and cleaned.endswith("*/")
            and not cleaned.startswith("/**")
        ):
            cleaned = cleaned[2:-2].strip()

        return cleaned
