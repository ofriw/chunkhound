"""JavaScript language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

try:
    from tree_sitter import Node as TSNode

    JAVASCRIPT_AVAILABLE = True
except ImportError:
    JAVASCRIPT_AVAILABLE = False
    TSNode = None


class JavaScriptParser(TreeSitterParserBase):
    """JavaScript language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize JavaScript parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.JAVASCRIPT, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for JavaScript parser."""
        return ParseConfig(
            language=CoreLanguage.JAVASCRIPT,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.METHOD,
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
        """Extract semantic chunks from JavaScript AST.

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

        # Extract React components
        if ChunkType.FUNCTION in self._config.chunk_types:
            chunks.extend(self._extract_components(tree_node, source, file_path))

        # Extract comments
        if ChunkType.COMMENT in self._config.chunk_types:
            comment_patterns = ["(comment) @comment"]
            chunks.extend(
                self._extract_comments_generic(
                    tree_node, source, file_path, comment_patterns
                )
            )

        # Extract JSDoc comments as docstrings
        if ChunkType.DOCSTRING in self._config.chunk_types:
            docstring_patterns = [("(comment) @jsdoc", "jsdoc")]
            # Filter for JSDoc-style comments only
            jsdoc_chunks = []
            for chunk in self._extract_docstrings_generic(
                tree_node, source, file_path, docstring_patterns
            ):
                if chunk["code"].strip().startswith("/**"):
                    jsdoc_chunks.append(chunk)
            chunks.extend(jsdoc_chunks)

        return chunks

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract JavaScript function declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (function_declaration
                    name: (identifier) @function_name
                ) @function_def

                (function_expression
                    name: (identifier) @function_name
                ) @function_expr_def

                (variable_declarator
                    name: (identifier) @var_name
                    value: (arrow_function) @arrow_func
                ) @var_function
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                function_node = None
                function_name = None

                if "function_def" in captures:
                    function_node = captures["function_def"][0]
                    if "function_name" in captures:
                        function_name_node = captures["function_name"][0]
                        function_name = self._get_node_text(function_name_node, source)
                elif "function_expr_def" in captures:
                    function_node = captures["function_expr_def"][0]
                    if "function_name" in captures:
                        function_name_node = captures["function_name"][0]
                        function_name = self._get_node_text(function_name_node, source)
                elif "var_function" in captures and "var_name" in captures:
                    function_node = captures["var_function"][0]
                    var_name_node = captures["var_name"][0]
                    function_name = self._get_node_text(var_name_node, source)

                if not function_node or not function_name:
                    continue

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
            logger.error(f"Failed to extract JavaScript functions: {e}")

        return chunks

    def _extract_classes(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract JavaScript class declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration
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
            logger.error(f"Failed to extract JavaScript classes: {e}")

        return chunks

    def _extract_components(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract React component declarations from JavaScript/JSX."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Look for function components (functions returning JSX)
            query = self._language.query("""
                (function_declaration
                    name: (identifier) @component_name
                ) @component_def

                (variable_declarator
                    name: (identifier) @component_name
                    value: (arrow_function) @arrow_component
                ) @var_component
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                component_node = None
                component_name = None

                if "component_def" in captures and "component_name" in captures:
                    component_node = captures["component_def"][0]
                    component_name_node = captures["component_name"][0]
                    component_name = self._get_node_text(component_name_node, source)

                    # Check if it's likely a React component (starts with capital letter)
                    if not component_name[0].isupper():
                        continue

                elif "var_component" in captures and "component_name" in captures:
                    component_node = captures["var_component"][0]
                    component_name_node = captures["component_name"][0]
                    component_name = self._get_node_text(component_name_node, source)

                    # Check if it's likely a React component (starts with capital letter)
                    if not component_name[0].isupper():
                        continue

                if not component_node or not component_name:
                    continue

                # Extract props parameters
                parameters = self._extract_function_parameters(component_node, source)
                param_str = ", ".join(parameters)

                display_name = f"{component_name}({param_str})"

                chunk = self._create_chunk(
                    component_node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    component_name,
                    display_name,
                    parameters=parameters,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract JavaScript components: {e}")

        return chunks

    def _extract_class_methods(
        self, class_node: TSNode, source: str, file_path: Path, class_name: str
    ) -> list[dict[str, Any]]:
        """Extract methods from a JavaScript class."""
        chunks = []

        try:
            # Find the class body
            body_node = None
            for i in range(class_node.child_count):
                child = class_node.child(i)
                if child and child.type == "class_body":
                    body_node = child
                    break

            if not body_node:
                return chunks

            # Query for methods within the class body
            if self._language is None:
                return chunks

            query = self._language.query("""
                (method_definition) @method_def
            """)

            matches = query.matches(body_node)

            for match in matches:
                pattern_index, captures = match

                if "method_def" not in captures:
                    continue

                method_node = captures["method_def"][0]

                # Extract method name from the method_definition node
                method_name = None
                for i in range(method_node.child_count):
                    child = method_node.child(i)
                    if child and child.type in ["identifier", "property_identifier"]:
                        method_name = self._get_node_text(child, source)
                        break

                if not method_name:
                    continue

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
            logger.error(f"Failed to extract JavaScript class methods: {e}")

        return chunks

    def _extract_function_parameters(
        self, function_node: TSNode, source: str
    ) -> list[str]:
        """Extract parameter names from a JavaScript function."""
        parameters = []

        try:
            if self._language is None:
                return parameters

            # Find the parameters node
            params_node = None
            for i in range(function_node.child_count):
                child = function_node.child(i)
                if child and child.type in ["formal_parameters", "parameters"]:
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
                elif child and child.type == "assignment_pattern":
                    # Handle default parameters
                    left_child = child.child(0)
                    if left_child and left_child.type == "identifier":
                        param_name = self._get_node_text(left_child, source).strip()
                        if param_name:
                            parameters.append(param_name)

        except Exception as e:
            logger.error(f"Failed to extract JavaScript function parameters: {e}")

        return parameters
