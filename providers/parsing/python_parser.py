"""Python language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    tspython = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class PythonParser:
    """Python language parser using tree-sitter."""

    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize Python parser.

        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False

        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.PYTHON,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.METHOD,
                ChunkType.BLOCK
            },
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=True,
            include_comments=False,
            include_docstrings=True,
            max_depth=10,
            use_cache=True
        )

        # Initialize if available
        if TREE_SITTER_AVAILABLE:
            self._initialize()

    def _initialize(self) -> bool:
        """Initialize the Python parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not TREE_SITTER_AVAILABLE:
            logger.error("Python tree-sitter support not available")
            return False

        try:
            if tspython and TSLanguage and TSParser:
                self._language = TSLanguage(tspython.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Python parser initialized successfully")
                return True
            else:
                logger.error("Python parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Python parser: {e}")
            return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.PYTHON

    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return TREE_SITTER_AVAILABLE and self._initialized

    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a Python file and extract semantic chunks.

        Args:
            file_path: Path to Python file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("Python parser not available")
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

            # Parse with tree-sitter
            if self._parser is None:
                errors.append("Python parser not initialized")
                return ParseResult(
                    chunks=chunks,
                    language=self.language,
                    total_chunks=0,
                    parse_time=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                    metadata={"file_path": str(file_path)}
                )

            tree = self._parser.parse(bytes(source, 'utf8'))

            # Extract semantic units
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_functions(tree.root_node, source, file_path))

            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(self._extract_classes(tree.root_node, source, file_path))

            # Fallback: create a BLOCK chunk if no structured chunks were found
            if len(chunks) == 0 and ChunkType.BLOCK in self._config.chunk_types:
                chunks.append(self._create_fallback_block_chunk(source, file_path))
                logger.debug(f"Created fallback BLOCK chunk for {file_path}")

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse Python file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={"file_path": str(file_path)}
        )

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte:node.end_byte]

    def _extract_functions(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract Python function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (function_definition
                    name: (identifier) @function_name
                ) @function_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "function_def" not in captures or "function_name" not in captures:
                    continue

                function_node = captures["function_def"][0]
                function_name_node = captures["function_name"][0]
                function_name = self._get_node_text(function_name_node, source)

                function_text = self._get_node_text(function_node, source)

                # Extract parameters
                parameters = self._extract_function_parameters(function_node, source)
                param_str = ", ".join(parameters)

                display_name = f"{function_name}({param_str})"

                chunk = {
                    "symbol": function_name,
                    "start_line": function_node.start_point[0] + 1,
                    "end_line": function_node.end_point[0] + 1,
                    "code": function_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "python",
                    "path": str(file_path),
                    "name": function_name,
                    "display_name": display_name,
                    "content": function_text,
                    "start_byte": function_node.start_byte,
                    "end_byte": function_node.end_byte,
                    "parameters": parameters,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python functions: {e}")

        return chunks

    def _extract_classes(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract Python class definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_definition
                    name: (identifier) @class_name
                ) @class_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "class_def" not in captures or "class_name" not in captures:
                    continue

                class_node = captures["class_def"][0]
                class_name_node = captures["class_name"][0]
                class_name = self._get_node_text(class_name_node, source)

                class_text = self._get_node_text(class_node, source)

                chunk = {
                    "symbol": class_name,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "python",
                    "path": str(file_path),
                    "name": class_name,
                    "display_name": class_name,
                    "content": class_text,
                    "start_byte": class_node.start_byte,
                    "end_byte": class_node.end_byte,
                }

                chunks.append(chunk)

                # Extract methods from class
                if ChunkType.METHOD in self._config.chunk_types:
                    method_chunks = self._extract_class_methods(class_node, source, file_path, class_name)
                    chunks.extend(method_chunks)

        except Exception as e:
            logger.error(f"Failed to extract Python classes: {e}")

        return chunks

    def _extract_class_methods(self, class_node: TSNode, source: str,
                              file_path: Path, class_name: str) -> List[Dict[str, Any]]:
        """Extract methods from a Python class."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Find the class body
            body_node = None
            for i in range(class_node.child_count):
                child = class_node.child(i)
                if child and child.type == "block":
                    body_node = child
                    break

            if not body_node:
                return chunks

            # Query for methods within the class body
            query = self._language.query("""
                (function_definition
                    name: (identifier) @method_name
                ) @method_def
            """)

            matches = query.matches(body_node)

            for match in matches:
                pattern_index, captures = match

                if "method_def" not in captures or "method_name" not in captures:
                    continue

                method_node = captures["method_def"][0]
                method_name_node = captures["method_name"][0]
                method_name = self._get_node_text(method_name_node, source)

                method_text = self._get_node_text(method_node, source)

                # Extract parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_str = ", ".join(parameters)

                qualified_name = f"{class_name}.{method_name}"
                display_name = f"{qualified_name}({param_str})"

                chunk = {
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "python",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parent": class_name,
                    "parameters": parameters,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python class methods: {e}")

        return chunks

    def _extract_function_parameters(self, function_node: TSNode, source: str) -> List[str]:
        """Extract parameter names from a Python function."""
        parameters = []

        try:
            if self._language is None:
                return parameters

            # Find the parameters node
            params_node = None
            for i in range(function_node.child_count):
                child = function_node.child(i)
                if child and child.type == "parameters":
                    params_node = child
                    break

            if not params_node:
                return parameters

            # Extract each parameter
            for i in range(params_node.child_count):
                child = params_node.child(i)
                if child and child.type == "identifier":
                    param_name = self._get_node_text(child, source).strip()
                    if param_name and param_name != "," and param_name != "(" and param_name != ")":
                        parameters.append(param_name)
                elif child and child.type == "default_parameter":
                    # Handle default parameters
                    name_child = child.child(0)
                    if name_child and name_child.type == "identifier":
                        param_name = self._get_node_text(name_child, source).strip()
                        if param_name:
                            parameters.append(param_name)

        except Exception as e:
            logger.error(f"Failed to extract Python function parameters: {e}")

        return parameters

    def _create_fallback_block_chunk(self, source: str, file_path: Path) -> Dict[str, Any]:
        """Create a fallback BLOCK chunk for files with no structured content.

        Args:
            source: Full source code of the file
            file_path: Path to the source file

        Returns:
            Dictionary representing a BLOCK chunk containing the entire file
        """
        # Count lines for proper line numbers
        lines = source.splitlines()
        line_count = len(lines)

        # Create a meaningful symbol name from the file
        file_stem = file_path.stem
        symbol = f"file:{file_stem}"

        # Use the filename as display name
        display_name = file_path.name

        chunk = {
            "symbol": symbol,
            "start_line": 1,
            "end_line": line_count,
            "code": source,
            "chunk_type": ChunkType.BLOCK.value,
            "language": "python",
            "path": str(file_path),
            "name": symbol,
            "display_name": display_name,
            "content": source,
            "start_byte": 0,
            "end_byte": len(source.encode('utf-8')),
        }

        return chunk
