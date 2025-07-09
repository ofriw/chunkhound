"""TypeScript language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

try:
    from tree_sitter import Node as TSNode

    TYPESCRIPT_AVAILABLE = True
except ImportError:
    TYPESCRIPT_AVAILABLE = False
    TSNode = None


class TypeScriptParser(TreeSitterParserBase):
    """TypeScript language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize TypeScript parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.TYPESCRIPT, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for TypeScript parser."""
        return ParseConfig(
            language=CoreLanguage.TYPESCRIPT,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.INTERFACE,
                ChunkType.METHOD,
                ChunkType.ENUM,
                ChunkType.TYPE_ALIAS,
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
        """Get tree-sitter language name for TypeScript."""
        return "typescript"

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from TypeScript AST.

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

        # Extract interfaces
        if ChunkType.INTERFACE in self._config.chunk_types:
            chunks.extend(self._extract_interfaces(tree_node, source, file_path))

        # Extract enums
        if ChunkType.ENUM in self._config.chunk_types:
            chunks.extend(self._extract_enums(tree_node, source, file_path))

        # Extract type aliases
        if ChunkType.TYPE_ALIAS in self._config.chunk_types:
            chunks.extend(self._extract_type_aliases(tree_node, source, file_path))

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
        """Extract TypeScript function declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (function_declaration
                    name: (identifier) @function_name
                ) @function_def

                (variable_declarator
                    name: (identifier) @function_name
                    value: (arrow_function) @arrow_function_def
                )

                (function_expression
                    name: (identifier) @function_name
                ) @function_expr_def
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
                elif "arrow_function_def" in captures and "function_name" in captures:
                    # Arrow function assigned to variable
                    function_node = captures["arrow_function_def"][0]
                    function_name_node = captures["function_name"][0]
                    function_name = self._get_node_text(function_name_node, source)
                elif "function_expr_def" in captures:
                    function_node = captures["function_expr_def"][0]
                    if "function_name" in captures:
                        function_name_node = captures["function_name"][0]
                        function_name = self._get_node_text(function_name_node, source)

                if not function_node or not function_name:
                    continue

                # Extract parameters
                parameters = self._extract_function_parameters(function_node, source)
                param_types_str = ", ".join(parameters)

                # Extract return type
                return_type = self._extract_function_return_type(function_node, source)

                display_name = f"{function_name}({param_types_str})"
                if return_type:
                    display_name += f": {return_type}"

                chunk = self._create_chunk(
                    function_node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    function_name,
                    display_name,
                    parameters=parameters,
                )

                if return_type:
                    chunk["return_type"] = return_type

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript functions: {e}")

        return chunks

    def _extract_classes(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract TypeScript class declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (class_declaration
                    name: (type_identifier) @class_name
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

                # Extract type parameters
                type_params = self._extract_type_parameters(class_node, source)
                if type_params:
                    display_name = f"{class_name}{type_params}"
                else:
                    display_name = class_name

                chunk = self._create_chunk(
                    class_node,
                    source,
                    file_path,
                    ChunkType.CLASS,
                    class_name,
                    display_name,
                )

                chunks.append(chunk)

                # Extract methods from class
                if ChunkType.METHOD in self._config.chunk_types:
                    method_chunks = self._extract_class_methods(
                        class_node, source, file_path, class_name
                    )
                    chunks.extend(method_chunks)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript classes: {e}")

        return chunks

    def _extract_interfaces(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract TypeScript interface declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (interface_declaration
                    name: (type_identifier) @interface_name
                ) @interface_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "interface_def" not in captures or "interface_name" not in captures:
                    continue

                interface_node = captures["interface_def"][0]
                interface_name_node = captures["interface_name"][0]
                interface_name = self._get_node_text(interface_name_node, source)

                # Extract type parameters
                type_params = self._extract_type_parameters(interface_node, source)
                if type_params:
                    display_name = f"{interface_name}{type_params}"
                else:
                    display_name = interface_name

                chunk = self._create_chunk(
                    interface_node,
                    source,
                    file_path,
                    ChunkType.INTERFACE,
                    interface_name,
                    display_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript interfaces: {e}")

        return chunks

    def _extract_enums(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract TypeScript enum declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (enum_declaration
                    name: (identifier) @enum_name
                ) @enum_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "enum_def" not in captures or "enum_name" not in captures:
                    continue

                enum_node = captures["enum_def"][0]
                enum_name_node = captures["enum_name"][0]
                enum_name = self._get_node_text(enum_name_node, source)

                chunk = self._create_chunk(
                    enum_node, source, file_path, ChunkType.ENUM, enum_name, enum_name
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript enums: {e}")

        return chunks

    def _extract_type_aliases(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract TypeScript type alias declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (type_alias_declaration
                    name: (type_identifier) @type_name
                ) @type_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "type_def" not in captures or "type_name" not in captures:
                    continue

                type_node = captures["type_def"][0]
                type_name_node = captures["type_name"][0]
                type_name = self._get_node_text(type_name_node, source)

                # Extract type parameters
                type_params = self._extract_type_parameters(type_node, source)
                if type_params:
                    display_name = f"{type_name}{type_params}"
                else:
                    display_name = type_name

                chunk = self._create_chunk(
                    type_node,
                    source,
                    file_path,
                    ChunkType.TYPE_ALIAS,
                    type_name,
                    display_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript type aliases: {e}")

        return chunks

    def _extract_components(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract React component declarations from TypeScript/TSX."""
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
                param_types_str = ", ".join(parameters)

                display_name = f"{component_name}({param_types_str})"

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
            logger.error(f"Failed to extract TypeScript components: {e}")

        return chunks

    def _extract_class_methods(
        self, class_node: TSNode, source: str, file_path: Path, class_name: str
    ) -> list[dict[str, Any]]:
        """Extract methods from a TypeScript class."""
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
                (method_definition
                    name: (_) @method_name
                ) @method_def

                (method_signature
                    name: (_) @method_name
                ) @method_sig
            """)

            matches = query.matches(body_node)

            for match in matches:
                pattern_index, captures = match
                method_node = None
                method_name = None

                if "method_def" in captures and "method_name" in captures:
                    method_node = captures["method_def"][0]
                    method_name_node = captures["method_name"][0]
                    method_name = self._get_node_text(method_name_node, source)
                elif "method_sig" in captures and "method_name" in captures:
                    method_node = captures["method_sig"][0]
                    method_name_node = captures["method_name"][0]
                    method_name = self._get_node_text(method_name_node, source)

                if not method_node or not method_name:
                    continue

                # Extract parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_types_str = ", ".join(parameters)

                # Extract return type
                return_type = self._extract_function_return_type(method_node, source)

                qualified_name = f"{class_name}.{method_name}"
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name += f": {return_type}"

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

                if return_type:
                    chunk["return_type"] = return_type

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript class methods: {e}")

        return chunks

    def _extract_type_parameters(self, node: TSNode, source: str) -> str:
        """Extract generic type parameters from a TypeScript node."""
        try:
            if self._language is None:
                return ""
            # Look for type_parameters node as a child
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "type_parameters":
                    return self._get_node_text(child, source).strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to extract TypeScript type parameters: {e}")
            return ""

    def _extract_function_parameters(
        self, function_node: TSNode, source: str
    ) -> list[str]:
        """Extract parameter types from a TypeScript function."""
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
                if child and child.type in ["required_parameter", "optional_parameter"]:
                    # Get parameter with type annotation
                    param_text = self._get_node_text(child, source).strip()
                    if (
                        param_text
                        and param_text != ","
                        and param_text != "("
                        and param_text != ")"
                    ):
                        parameters.append(param_text)

        except Exception as e:
            logger.error(f"Failed to extract TypeScript function parameters: {e}")

        return parameters

    def _extract_function_return_type(
        self, function_node: TSNode, source: str
    ) -> str | None:
        """Extract return type from a TypeScript function."""
        try:
            if self._language is None:
                return None

            # Use tree-sitter query to find type annotations
            query = self._language.query("""
                (type_annotation) @return_type
            """)

            matches = query.matches(function_node)
            for match in matches:
                _, captures = match
                if "return_type" in captures:
                    type_node = captures["return_type"][0]
                    return self._get_node_text(type_node, source).strip()

            return None
        except Exception as e:
            logger.error(f"Failed to extract TypeScript function return type: {e}")
            return None
