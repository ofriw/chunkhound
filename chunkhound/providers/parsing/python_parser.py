"""Python language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

try:
    from tree_sitter import Node as TSNode

    PYTHON_AVAILABLE = True
except ImportError:
    PYTHON_AVAILABLE = False
    TSNode = None


class PythonParser(TreeSitterParserBase):
    """Python language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Python parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.PYTHON, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for Python parser."""
        return ParseConfig(
            language=CoreLanguage.PYTHON,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.METHOD,
                ChunkType.BLOCK,
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

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from Python AST.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file

        Returns:
            List of extracted chunks
        """
        chunks = []

        # Extract functions
        if ChunkType.FUNCTION in self._config.chunk_types:
            chunks.extend(self._extract_functions(tree_node, source, file_path))

        # Extract classes
        if ChunkType.CLASS in self._config.chunk_types:
            chunks.extend(self._extract_classes(tree_node, source, file_path))

        # Extract docstrings
        if ChunkType.DOCSTRING in self._config.chunk_types:
            chunks.extend(self._extract_docstrings(tree_node, source, file_path))

        # Extract comments
        if ChunkType.COMMENT in self._config.chunk_types:
            chunks.extend(self._extract_comments(tree_node, source, file_path))

        # Fallback: create a BLOCK chunk if no structured chunks were found
        if len(chunks) == 0 and ChunkType.BLOCK in self._config.chunk_types:
            chunks.append(self._create_fallback_block_chunk(source, file_path))
            logger.debug(f"Created fallback BLOCK chunk for {file_path}")

        return chunks

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
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
                function_name = self._get_node_text(function_name_node, source).strip()

                # Fallback for empty function names
                if not function_name:
                    function_name = f"function_{function_node.start_point[0] + 1}"

                function_text = self._get_node_text(function_node, source)

                # Extract parameters
                parameters = self._extract_function_parameters(function_node, source)
                param_str = ", ".join(parameters)

                display_name = f"{function_name}({param_str})"

                chunk = self._create_chunk(
                    function_node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    function_name,
                    display_name,
                    parameters=parameters,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python functions: {e}")

        return chunks

    def _extract_classes(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
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
                class_name = self._get_node_text(class_name_node, source).strip()

                # Fallback for empty class names
                if not class_name:
                    class_name = f"class_{class_node.start_point[0] + 1}"

                class_text = self._get_node_text(class_node, source)

                chunk = self._create_chunk(
                    class_node, source, file_path, ChunkType.CLASS, class_name
                )

                chunks.append(chunk)

                # Extract methods from class
                if ChunkType.METHOD in self._config.chunk_types:
                    method_chunks = self._extract_class_methods(
                        class_node, source, file_path, class_name
                    )
                    chunks.extend(method_chunks)

        except Exception as e:
            logger.error(f"Failed to extract Python classes: {e}")

        return chunks

    def _extract_class_methods(
        self, class_node: TSNode, source: str, file_path: Path, class_name: str
    ) -> list[dict[str, Any]]:
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
                method_name = self._get_node_text(method_name_node, source).strip()

                # Fallback for empty method names
                if not method_name:
                    method_name = f"method_{method_node.start_point[0] + 1}"

                method_text = self._get_node_text(method_node, source)

                # Extract parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_str = ", ".join(parameters)

                qualified_name = f"{class_name}.{method_name}"
                display_name = f"{qualified_name}({param_str})"

                chunk = self._create_chunk(
                    method_node,
                    source,
                    file_path,
                    ChunkType.METHOD,
                    qualified_name,
                    display_name,
                    parent=class_name,
                    parameters=parameters,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python class methods: {e}")

        return chunks

    def _extract_function_parameters(
        self, function_node: TSNode, source: str
    ) -> list[str]:
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
                    if (
                        param_name
                        and param_name != ","
                        and param_name != "("
                        and param_name != ")"
                    ):
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

    def _create_fallback_block_chunk(
        self, source: str, file_path: Path
    ) -> dict[str, Any]:
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
            "end_byte": len(source.encode("utf-8")),
        }

        return chunk

    def _extract_docstrings(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Python docstrings from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for all string nodes that are docstrings
            query = self._language.query("""
                (module . (expression_statement (string) @module_docstring))
                (function_definition body: (block . (expression_statement (string) @function_docstring)))
                (class_definition body: (block . (expression_statement (string) @class_docstring)))
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                # Process each capture type
                for capture_name, nodes in captures.items():
                    for node in nodes:
                        docstring_text = self._get_node_text(node, source)

                        # Skip empty docstrings
                        if not docstring_text.strip():
                            continue

                        # Remove quotes and clean up
                        cleaned_text = docstring_text.strip()
                        if cleaned_text.startswith('"""') or cleaned_text.startswith(
                            "'''"
                        ):
                            cleaned_text = cleaned_text[3:-3].strip()
                        elif cleaned_text.startswith('"') or cleaned_text.startswith(
                            "'"
                        ):
                            cleaned_text = cleaned_text[1:-1].strip()

                        # Determine context based on capture name
                        context = "module"
                        if "function" in capture_name:
                            context = "function"
                        elif "class" in capture_name:
                            context = "class"

                        symbol = f"docstring:{context}:{node.start_point[0] + 1}"

                        chunk = self._create_chunk(
                            node,
                            source,
                            file_path,
                            ChunkType.DOCSTRING,
                            symbol,
                            f"{context.capitalize()} docstring",
                            content=cleaned_text,
                            context=context,
                        )

                        chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python docstrings: {e}")

        return chunks

    def _extract_comments(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Python comments from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for comment nodes
            query = self._language.query("""
                (comment) @comment
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "comment" not in captures:
                    continue

                for comment_node in captures["comment"]:
                    comment_text = self._get_node_text(comment_node, source)

                    # Clean up comment text
                    cleaned_text = comment_text.strip()
                    if cleaned_text.startswith("#"):
                        cleaned_text = cleaned_text[1:].strip()

                    symbol = f"comment:{comment_node.start_point[0] + 1}"

                    chunk = self._create_chunk(
                        comment_node,
                        source,
                        file_path,
                        ChunkType.COMMENT,
                        symbol,
                        f"Comment at line {comment_node.start_point[0] + 1}",
                        content=cleaned_text,
                    )

                    chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Python comments: {e}")

        return chunks
