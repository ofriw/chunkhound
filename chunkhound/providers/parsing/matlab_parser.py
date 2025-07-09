"""Matlab language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

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


class MatlabParser(TreeSitterParserBase):
    """Matlab language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Matlab parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.MATLAB, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for Matlab parser."""
        return ParseConfig(
            language=CoreLanguage.MATLAB,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.METHOD,
                ChunkType.SCRIPT,
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

    def _get_tree_sitter_language_name(self) -> str:
        """Get tree-sitter language name for Matlab."""
        return "matlab"

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from Matlab AST.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file

        Returns:
            List of extracted chunks
        """
        chunks = []

        try:
            # Extract functions
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_functions(tree_node, source, file_path))

            # Extract classes
            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(self._extract_classes(tree_node, source, file_path))

            # Extract script-level code blocks
            if ChunkType.SCRIPT in self._config.chunk_types:
                script_chunks = self._extract_script_blocks(
                    tree_node, source, file_path
                )
                chunks.extend(script_chunks)

            # Extract comments
            if ChunkType.COMMENT in self._config.chunk_types:
                comment_patterns = ["(comment) @comment"]
                chunks.extend(
                    self._extract_comments_generic(
                        tree_node, source, file_path, comment_patterns
                    )
                )

            # Extract docstrings (Matlab help text)
            if ChunkType.DOCSTRING in self._config.chunk_types:
                docstring_patterns = [("(comment) @help_text", "help")]
                # Filter for help text (multiline comments starting with %%)
                help_chunks = []
                for chunk in self._extract_docstrings_generic(
                    tree_node, source, file_path, docstring_patterns
                ):
                    if chunk["code"].strip().startswith("%%"):
                        help_chunks.append(chunk)
                chunks.extend(help_chunks)

            # Fallback: create a BLOCK chunk if no structured chunks were found
            if len(chunks) == 0 and ChunkType.BLOCK in self._config.chunk_types:
                chunks.append(self._create_fallback_block_chunk(source, file_path))
                logger.debug(f"Created fallback BLOCK chunk for {file_path}")

        except Exception as e:
            logger.error(f"Failed to extract chunks from Matlab file: {e}")

        return chunks

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Matlab function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for function definitions
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

                # Extract parameters and return values
                parameters, return_values = self._extract_function_signature(
                    function_node, source
                )

                # Create display name with Matlab-style signature
                if return_values:
                    if len(return_values) == 1:
                        display_name = f"{return_values[0]} = {function_name}({', '.join(parameters)})"
                    else:
                        display_name = f"[{', '.join(return_values)}] = {function_name}({', '.join(parameters)})"
                else:
                    display_name = f"{function_name}({', '.join(parameters)})"

                chunk = self._create_chunk(
                    function_node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    function_name,
                    display_name=display_name,
                    parameters=parameters,
                    return_values=return_values,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Matlab functions: {e}")

        return chunks

    def _extract_classes(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Matlab class definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for class definitions
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

                # Extract inheritance information
                inheritance = self._extract_class_inheritance(class_node, source)
                display_name = f"{class_name}"
                if inheritance:
                    display_name += f" < {', '.join(inheritance)}"

                chunk = self._create_chunk(
                    class_node,
                    source,
                    file_path,
                    ChunkType.CLASS,
                    class_name,
                    display_name=display_name,
                    inheritance=inheritance,
                )

                chunks.append(chunk)

                # Extract methods from class
                if ChunkType.METHOD in self._config.chunk_types:
                    method_chunks = self._extract_class_methods(
                        class_node, source, file_path, class_name
                    )
                    chunks.extend(method_chunks)

        except Exception as e:
            logger.error(f"Failed to extract Matlab classes: {e}")

        return chunks

    def _extract_class_methods(
        self, class_node: TSNode, source: str, file_path: Path, class_name: str
    ) -> list[dict[str, Any]]:
        """Extract methods from a Matlab class."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for methods within the class - use broader approach
            query = self._language.query("""
                (function_definition
                    name: (identifier) @method_name
                ) @method_def
            """)

            matches = query.matches(class_node)

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

                # Extract parameters and return values
                parameters, return_values = self._extract_function_signature(
                    method_node, source
                )

                qualified_name = f"{class_name}.{method_name}"

                # Create display name with Matlab-style signature
                if return_values:
                    if len(return_values) == 1:
                        display_name = f"{return_values[0]} = {qualified_name}({', '.join(parameters)})"
                    else:
                        display_name = f"[{', '.join(return_values)}] = {qualified_name}({', '.join(parameters)})"
                else:
                    display_name = f"{qualified_name}({', '.join(parameters)})"

                chunk = self._create_chunk(
                    method_node,
                    source,
                    file_path,
                    ChunkType.METHOD,
                    qualified_name,
                    display_name=display_name,
                    parent=class_name,
                    parameters=parameters,
                    return_values=return_values,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Matlab class methods: {e}")

        return chunks

    def _extract_script_blocks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract script-level code blocks from Matlab files."""
        chunks = []

        try:
            # Check if this is a script file (no function definitions at top level)
            has_functions = self._has_top_level_functions(tree_node)

            if not has_functions:
                # This is a script file - create a script chunk
                script_name = f"script:{file_path.stem}"

                chunk = self._create_chunk(
                    tree_node,
                    source,
                    file_path,
                    ChunkType.SCRIPT,
                    script_name,
                    display_name=file_path.name,
                )
                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Matlab script blocks: {e}")

        return chunks

    def _extract_function_signature(
        self, function_node: TSNode, source: str
    ) -> tuple[list[str], list[str]]:
        """Extract parameter names and return values from a Matlab function."""
        parameters = []
        return_values = []

        try:
            if self._language is None:
                return parameters, return_values

            # Look for function signature components
            for child in function_node.children:
                if child.type == "function_output":
                    # Extract return values
                    return_values = self._extract_identifiers_from_node(child, source)
                elif child.type == "function_arguments":
                    # Extract parameters
                    parameters = self._extract_identifiers_from_node(child, source)

        except Exception as e:
            logger.error(f"Failed to extract Matlab function signature: {e}")

        return parameters, return_values

    def _extract_class_inheritance(self, class_node: TSNode, source: str) -> list[str]:
        """Extract inheritance information from a Matlab class."""
        inheritance = []

        try:
            # Look for inheritance syntax: classdef MyClass < BaseClass
            # Parse the class definition line manually since tree-sitter structure may vary
            class_text = self._get_node_text(class_node, source)
            lines = class_text.split("\n")
            if lines:
                first_line = lines[0]
                if "<" in first_line:
                    # Extract inheritance from "classdef ClassName < BaseClass"
                    parts = first_line.split("<")
                    if len(parts) > 1:
                        base_classes = parts[1].strip()
                        # Handle multiple inheritance separated by &
                        inheritance = [cls.strip() for cls in base_classes.split("&")]

        except Exception as e:
            logger.error(f"Failed to extract Matlab class inheritance: {e}")

        return inheritance

    def _extract_identifiers_from_node(self, node: TSNode, source: str) -> list[str]:
        """Extract all identifier names from a node."""
        identifiers = []

        try:
            if node.type == "identifier":
                name = self._get_node_text(node, source).strip()
                if name:
                    identifiers.append(name)
            else:
                # Recursively search for identifiers
                for child in node.children:
                    identifiers.extend(
                        self._extract_identifiers_from_node(child, source)
                    )

        except Exception as e:
            logger.error(f"Failed to extract identifiers from node: {e}")

        return identifiers

    def _has_top_level_functions(self, tree_node: TSNode) -> bool:
        """Check if the file has top-level function definitions."""
        try:
            if self._language is None:
                return False

            query = self._language.query("""
                (function_definition) @function_def
            """)

            matches = query.matches(tree_node)

            # Check if any function is at the top level (not nested)
            for match in matches:
                pattern_index, captures = match
                if "function_def" in captures:
                    function_node = captures["function_def"][0]
                    # If function is a direct child of root, it's top-level
                    if function_node.parent == tree_node:
                        return True

        except Exception as e:
            logger.error(f"Failed to check for top-level functions: {e}")

        return False

    def _create_fallback_block_chunk(
        self, source: str, file_path: Path
    ) -> dict[str, Any]:
        """Create a fallback BLOCK chunk for files with no structured content."""
        lines = source.splitlines()
        line_count = len(lines)

        file_stem = file_path.stem
        symbol = f"file:{file_stem}"
        display_name = file_path.name

        chunk = {
            "symbol": symbol,
            "start_line": 1,
            "end_line": line_count,
            "code": source,
            "chunk_type": ChunkType.BLOCK.value,
            "language": "matlab",
            "path": str(file_path),
            "name": symbol,
            "display_name": display_name,
            "content": source,
            "start_byte": 0,
            "end_byte": len(source.encode("utf-8")),
        }

        return chunk
