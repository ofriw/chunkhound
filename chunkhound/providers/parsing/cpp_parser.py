"""C++ language parser provider implementation for ChunkHound using tree-sitter."""

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

    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None

# Try direct import as fallback
try:
    import tree_sitter_cpp as ts_cpp

    CPP_DIRECT_AVAILABLE = True
except ImportError:
    CPP_DIRECT_AVAILABLE = False
    ts_cpp = None


class CppParser:
    """C++ language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize C++ parser.

        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False

        # Default configuration for C++-specific chunk types
        self._config = config or ParseConfig(
            language=CoreLanguage.CPP,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.NAMESPACE,
                ChunkType.ENUM,
                ChunkType.VARIABLE,
                ChunkType.TYPE,
                ChunkType.MACRO,
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
        if not CPP_AVAILABLE and not CPP_DIRECT_AVAILABLE:
            raise ImportError(
                "C++ tree-sitter dependencies not available - install tree-sitter-language-pack or tree-sitter-cpp"
            )

        if not self._initialize():
            raise RuntimeError("Failed to initialize C++ parser")

    def _initialize(self) -> bool:
        """Initialize the C++ parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not CPP_AVAILABLE and not CPP_DIRECT_AVAILABLE:
            logger.error("C++ tree-sitter support not available")
            return False

        # Try direct import first
        try:
            if CPP_DIRECT_AVAILABLE and ts_cpp and TSLanguage and TSParser:
                self._language = TSLanguage(ts_cpp.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("C++ parser initialized successfully (direct)")
                return True
        except Exception as e:
            logger.debug(f"Direct C++ parser initialization failed: {e}")

        # Fallback to language pack
        try:
            if CPP_AVAILABLE and get_language and get_parser:
                self._language = get_language("cpp")
                self._parser = get_parser("cpp")
                self._initialized = True
                logger.debug("C++ parser initialized successfully (language pack)")
                return True
        except Exception as e:
            logger.error(f"C++ parser language pack initialization failed: {e}")

        logger.error("C++ parser initialization failed with both methods")
        return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.CPP

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return (CPP_AVAILABLE or CPP_DIRECT_AVAILABLE) and self._initialized

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte : node.end_byte]

    def parse_file(self, file_path: Path, source: str | None = None) -> ParseResult:
        """Parse a C++ file and extract semantic chunks.

        Args:
            file_path: Path to C++ file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("C++ parser not available")
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
                errors.append("C++ parser not initialized")
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
            error_msg = f"Failed to parse C++ file {file_path}: {e}"
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
        """Extract semantic chunks from C++ AST.

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
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_functions(tree_node, source, file_path))

            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(self._extract_classes(tree_node, source, file_path))

            if ChunkType.NAMESPACE in self._config.chunk_types:
                chunks.extend(self._extract_namespaces(tree_node, source, file_path))

            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(self._extract_enums(tree_node, source, file_path))

            if ChunkType.VARIABLE in self._config.chunk_types:
                chunks.extend(self._extract_variables(tree_node, source, file_path))

            if ChunkType.TYPE in self._config.chunk_types:
                chunks.extend(self._extract_types(tree_node, source, file_path))

            if ChunkType.MACRO in self._config.chunk_types:
                chunks.extend(self._extract_macros(tree_node, source, file_path))

            # Extract comments and docstrings
            if ChunkType.COMMENT in self._config.chunk_types:
                chunks.extend(self._extract_comments(tree_node, source, file_path))

            if ChunkType.DOCSTRING in self._config.chunk_types:
                chunks.extend(self._extract_docstrings(tree_node, source, file_path))

        except Exception as e:
            logger.error(f"Failed to extract C++ chunks: {e}")

        return chunks

    def parse_content(
        self, content: str, file_path: Path = None
    ) -> list[dict[str, Any]]:
        """Parse C++ content string and extract semantic chunks.

        Args:
            content: C++ content to parse
            file_path: Optional file path for context

        Returns:
            List of chunk dictionaries
        """
        if not self.is_available:
            return []

        if file_path is None:
            file_path = Path("content.cpp")

        try:
            tree = self._parser.parse(bytes(content, "utf8"))
            return self._extract_chunks(tree.root_node, content, file_path)
        except Exception as e:
            logger.error(f"Error parsing C++ content: {e}")
            return []

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Simplified query for function definitions
            query = self._language.query("(function_definition) @function_def")

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "function_def" not in captures:
                    continue

                function_node = captures["function_def"][0]
                # Extract function name from the node text
                function_text = self._get_node_text(function_node, source)
                # Simple extraction - get the identifier from function signature
                lines = function_text.split("\n")[0]  # First line
                # Find the function name - look for pattern like "type name(" or "name("
                import re

                match = re.search(r"(\w+)\s*\(", lines)
                if match:
                    function_name = match.group(1)
                else:
                    function_name = "unknown_function"

                chunk = self._create_chunk(
                    function_node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    function_name,
                    function_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ functions: {e}")

        return chunks

    def _extract_classes(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ class, struct, and union definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for class, struct, and union declarations
            query = self._language.query("""
                (class_specifier
                    name: (type_identifier) @class_name
                ) @class_def

                (struct_specifier
                    name: (type_identifier) @struct_name
                ) @struct_def

                (union_specifier
                    name: (type_identifier) @union_name
                ) @union_def

                (template_declaration
                    (class_specifier
                        name: (type_identifier) @class_name
                    ) @class_def
                )

                (template_declaration
                    (struct_specifier
                        name: (type_identifier) @struct_name
                    ) @struct_def
                )
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                class_node = None
                class_name = None

                # Handle classes
                if "class_def" in captures and "class_name" in captures:
                    class_node = captures["class_def"][0]
                    class_name_node = captures["class_name"][0]
                    class_name = f"class {self._get_node_text(class_name_node, source)}"

                # Handle structs
                elif "struct_def" in captures and "struct_name" in captures:
                    class_node = captures["struct_def"][0]
                    struct_name_node = captures["struct_name"][0]
                    class_name = (
                        f"struct {self._get_node_text(struct_name_node, source)}"
                    )

                # Handle unions
                elif "union_def" in captures and "union_name" in captures:
                    class_node = captures["union_def"][0]
                    union_name_node = captures["union_name"][0]
                    class_name = f"union {self._get_node_text(union_name_node, source)}"

                if not class_node or not class_name:
                    continue

                chunk = self._create_chunk(
                    class_node,
                    source,
                    file_path,
                    ChunkType.CLASS,
                    class_name,
                    class_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ classes: {e}")

        return chunks

    def _extract_namespaces(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ namespace definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Simplified query for namespace definitions
            # Note: This might need adjustment based on tree-sitter-cpp grammar
            query = self._language.query("(namespace_definition) @namespace_def")

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "namespace_def" not in captures:
                    continue

                namespace_node = captures["namespace_def"][0]
                # Extract namespace name from the node text
                namespace_text = self._get_node_text(namespace_node, source)
                # Simple extraction - get the identifier after "namespace"
                lines = namespace_text.split("\n")[0]  # First line
                parts = lines.split()
                if len(parts) >= 2 and parts[0] == "namespace":
                    namespace_name = f"namespace {parts[1]}"
                else:
                    namespace_name = "namespace"

                chunk = self._create_chunk(
                    namespace_node,
                    source,
                    file_path,
                    ChunkType.NAMESPACE,
                    namespace_name,
                    namespace_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ namespaces: {e}")

        return chunks

    def _extract_enums(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ enum definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for enum definitions (including enum class)
            query = self._language.query("""
                (enum_specifier
                    name: (type_identifier) @enum_name
                ) @enum_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "enum_def" not in captures or "enum_name" not in captures:
                    continue

                enum_node = captures["enum_def"][0]
                enum_name_node = captures["enum_name"][0]
                enum_name = f"enum {self._get_node_text(enum_name_node, source)}"

                chunk = self._create_chunk(
                    enum_node, source, file_path, ChunkType.ENUM, enum_name, enum_name
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ enums: {e}")

        return chunks

    def _extract_variables(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ global variable declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for global variable declarations (not inside functions/classes)
            query = self._language.query("""
                (translation_unit
                    (declaration
                        declarator: (init_declarator
                            declarator: (identifier) @var_name
                        )
                    ) @var_def
                )

                (translation_unit
                    (declaration
                        declarator: (identifier) @var_name
                    ) @var_def
                )
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "var_def" not in captures or "var_name" not in captures:
                    continue

                var_node = captures["var_def"][0]
                var_name_node = captures["var_name"][0]
                var_name = self._get_node_text(var_name_node, source)

                chunk = self._create_chunk(
                    var_node, source, file_path, ChunkType.VARIABLE, var_name, var_name
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ variables: {e}")

        return chunks

    def _extract_types(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ type declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for type declarations (typedef, using, type aliases)
            query = self._language.query("""
                (type_definition
                    declarator: (type_identifier) @typedef_name
                ) @typedef_def

                (alias_declaration
                    name: (type_identifier) @alias_name
                ) @alias_def

                (using_declaration
                    (qualified_identifier
                        name: (identifier) @using_name
                    )
                ) @using_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                type_node = None
                type_name = None

                # Handle typedef
                if "typedef_def" in captures and "typedef_name" in captures:
                    type_node = captures["typedef_def"][0]
                    typedef_name_node = captures["typedef_name"][0]
                    type_name = (
                        f"typedef {self._get_node_text(typedef_name_node, source)}"
                    )

                # Handle using alias
                elif "alias_def" in captures and "alias_name" in captures:
                    type_node = captures["alias_def"][0]
                    alias_name_node = captures["alias_name"][0]
                    type_name = f"using {self._get_node_text(alias_name_node, source)}"

                # Handle using declaration
                elif "using_def" in captures and "using_name" in captures:
                    type_node = captures["using_def"][0]
                    using_name_node = captures["using_name"][0]
                    type_name = f"using {self._get_node_text(using_name_node, source)}"

                if not type_node or not type_name:
                    continue

                chunk = self._create_chunk(
                    type_node, source, file_path, ChunkType.TYPE, type_name, type_name
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ types: {e}")

        return chunks

    def _extract_macros(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ preprocessor macro definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for preprocessor definitions
            query = self._language.query("""
                (preproc_def
                    name: (identifier) @macro_name
                ) @macro_def

                (preproc_function_def
                    name: (identifier) @func_macro_name
                ) @func_macro_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                macro_node = None
                macro_name = None

                # Handle simple macros
                if "macro_def" in captures and "macro_name" in captures:
                    macro_node = captures["macro_def"][0]
                    macro_name_node = captures["macro_name"][0]
                    macro_name = (
                        f"#define {self._get_node_text(macro_name_node, source)}"
                    )

                # Handle function-like macros
                elif "func_macro_def" in captures and "func_macro_name" in captures:
                    macro_node = captures["func_macro_def"][0]
                    func_macro_name_node = captures["func_macro_name"][0]
                    macro_name = f"#define {self._get_node_text(func_macro_name_node, source)}(...)"

                if not macro_node or not macro_name:
                    continue

                chunk = self._create_chunk(
                    macro_node,
                    source,
                    file_path,
                    ChunkType.MACRO,
                    macro_name,
                    macro_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ macros: {e}")

        return chunks

    def _create_chunk(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunk_type: ChunkType,
        symbol: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create a chunk dictionary from a tree-sitter node.

        Args:
            node: Tree-sitter node
            source: Source code string
            file_path: Path to source file
            chunk_type: Type of chunk
            symbol: Symbol name
            display_name: Display name for the chunk

        Returns:
            Chunk dictionary
        """
        content = self._get_node_text(node, source)

        return {
            "symbol": symbol,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "code": content,
            "chunk_type": chunk_type.value,
            "language": "cpp",
            "path": str(file_path),
            "name": symbol,
            "display_name": display_name,
            "content": content,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }

    def _extract_comments(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ comments (// and /* */)."""
        comment_patterns = ["(comment) @comment"]
        return self._extract_comments_generic(
            tree_node, source, file_path, comment_patterns
        )

    def _extract_docstrings(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract C++ documentation comments (/** */ and ///)."""
        chunks = []

        if self._language is None:
            return chunks

        try:
            # Extract documentation comments (/** ... */ and ///)
            query = self._language.query("(comment) @comment")
            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                for capture_name, nodes in captures.items():
                    for node in nodes:
                        comment_text = self._get_node_text(node, source)

                        # Check if it's a documentation comment (starts with /** or ///)
                        if comment_text.strip().startswith(
                            "/**"
                        ) or comment_text.strip().startswith("///"):
                            cleaned_text = self._clean_doc_comment_text(comment_text)
                            symbol = f"doc:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node,
                                source,
                                file_path,
                                ChunkType.DOCSTRING,
                                symbol,
                                f"Documentation at line {node.start_point[0] + 1}",
                            )
                            chunk["content"] = cleaned_text

                            chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract C++ docstrings: {e}")

        return chunks

    def _clean_doc_comment_text(self, text: str) -> str:
        """Clean documentation comment text by removing markers and prefixes."""
        cleaned = text.strip()

        # Remove /** */ markers
        if cleaned.startswith("/**") and cleaned.endswith("*/"):
            cleaned = cleaned[3:-2]
        # Remove /// markers
        elif cleaned.startswith("///"):
            cleaned = cleaned[3:]

        # Remove leading * or / from each line
        lines = cleaned.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].lstrip()
            elif line.startswith("///"):
                line = line[3:].lstrip()
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

                            # Skip empty comments and doc comments (handled separately)
                            if (
                                not comment_text.strip()
                                or comment_text.strip().startswith("/**")
                                or comment_text.strip().startswith("///")
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

        except Exception as e:
            logger.error(f"Failed to extract comments for C++: {e}")

        return chunks

    def _clean_comment_text(self, text: str) -> str:
        """Clean comment text by removing comment markers."""
        cleaned = text.strip()

        # Remove common single-line comment markers
        if cleaned.startswith("//"):
            cleaned = cleaned[2:].strip()

        # Remove common multi-line comment markers (but not doc comments)
        if (
            cleaned.startswith("/*")
            and cleaned.endswith("*/")
            and not cleaned.startswith("/**")
        ):
            cleaned = cleaned[2:-2].strip()

        return cleaned
