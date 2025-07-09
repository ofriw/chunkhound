"""Go language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

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

    GO_AVAILABLE = True
except ImportError:
    GO_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None

# Try direct import as fallback
try:
    import tree_sitter_go as ts_go

    GO_DIRECT_AVAILABLE = True
except ImportError:
    GO_DIRECT_AVAILABLE = False
    ts_go = None


class GoParser:
    """Go language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Go parser.

        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False

        # Default configuration for Go-specific chunk types
        self._config = config or ParseConfig(
            language=CoreLanguage.GO,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.METHOD,
                ChunkType.STRUCT,
                ChunkType.INTERFACE,
                ChunkType.TYPE,
                ChunkType.VARIABLE,
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
        if not GO_AVAILABLE and not GO_DIRECT_AVAILABLE:
            raise ImportError(
                "Go tree-sitter dependencies not available - install tree-sitter-language-pack or tree-sitter-go"
            )

        if not self._initialize():
            raise RuntimeError("Failed to initialize Go parser")

    def _initialize(self) -> bool:
        """Initialize the Go parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not GO_AVAILABLE and not GO_DIRECT_AVAILABLE:
            logger.error("Go tree-sitter support not available")
            return False

        # Try direct import first
        try:
            if GO_DIRECT_AVAILABLE and ts_go and TSLanguage and TSParser:
                self._language = TSLanguage(ts_go.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Go parser initialized successfully (direct)")
                return True
        except Exception as e:
            logger.debug(f"Direct Go parser initialization failed: {e}")

        # Fallback to language pack
        try:
            if GO_AVAILABLE and get_language and get_parser:
                self._language = get_language("go")
                self._parser = get_parser("go")
                self._initialized = True
                logger.debug("Go parser initialized successfully (language pack)")
                return True
        except Exception as e:
            logger.error(f"Go parser language pack initialization failed: {e}")

        logger.error("Go parser initialization failed with both methods")
        return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.GO

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return (GO_AVAILABLE or GO_DIRECT_AVAILABLE) and self._initialized

    def parse_file(self, file_path: Path, source: str | None = None) -> ParseResult:
        """Parse a Go file and extract semantic chunks.

        Args:
            file_path: Path to Go file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("Go parser not available")
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
                errors.append("Go parser not initialized")
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

            # Extract package name for context
            package_name = self._extract_package(tree.root_node, source) if tree else ""

            # Extract semantic units
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(
                    self._extract_functions(
                        tree.root_node, source, file_path, package_name
                    )
                )

            if ChunkType.METHOD in self._config.chunk_types:
                chunks.extend(
                    self._extract_methods(
                        tree.root_node, source, file_path, package_name
                    )
                )

            if ChunkType.STRUCT in self._config.chunk_types:
                chunks.extend(
                    self._extract_structs(
                        tree.root_node, source, file_path, package_name
                    )
                )

            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(
                    self._extract_interfaces(
                        tree.root_node, source, file_path, package_name
                    )
                )

            if ChunkType.TYPE in self._config.chunk_types:
                chunks.extend(
                    self._extract_types(tree.root_node, source, file_path, package_name)
                )

            if ChunkType.VARIABLE in self._config.chunk_types:
                chunks.extend(
                    self._extract_variables(
                        tree.root_node, source, file_path, package_name
                    )
                )

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse Go file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            package_name = ""  # Set default value on error

        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={
                "file_path": str(file_path),
                "package_name": package_name if "package_name" in locals() else "",
            },
        )

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte : node.end_byte]

    def _extract_package(self, tree_node: TSNode, source: str) -> str:
        """Extract package name from Go file.

        Args:
            tree_node: Root node of the Go AST
            source: Source code content

        Returns:
            Package name as string, or empty string if no package declaration found
        """
        try:
            if self._language is None:
                return ""

            query = self._language.query("""
                (package_clause
                    (package_identifier) @package_name
                ) @package_def
            """)

            matches = query.matches(tree_node)

            if not matches:
                return ""

            # Get first match and extract package node
            pattern_index, captures = matches[0]
            if "package_name" not in captures:
                return ""

            package_node = captures["package_name"][0]
            package_name = self._get_node_text(package_node, source)

            return package_name.strip()
        except Exception as e:
            logger.error(f"Failed to extract Go package: {e}")
            return ""

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for function declarations (regular functions, not methods)
            query = self._language.query("""
                (function_declaration
                    name: (identifier) @func_name
                ) @func_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "func_def" not in captures or "func_name" not in captures:
                    continue

                func_node = captures["func_def"][0]
                func_name_node = captures["func_name"][0]
                func_name = self._get_node_text(func_name_node, source)

                # Get full function text
                func_text = self._get_node_text(func_node, source)

                # Build qualified name with package
                qualified_name = func_name
                if package_name:
                    qualified_name = f"{package_name}.{func_name}"

                # Get function parameters
                parameters = self._extract_function_parameters(func_node, source)
                param_types_str = ", ".join(parameters)

                # Get function return type
                return_type = self._extract_function_return_type(func_node, source)

                # Create display name
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name = f"{display_name} {return_type}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": func_node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "code": func_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "go",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": func_text,
                    "start_byte": func_node.start_byte,
                    "end_byte": func_node.end_byte,
                    "parameters": parameters,
                }

                if return_type:
                    chunk["return_type"] = return_type

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go functions: {e}")

        return chunks

    def _extract_methods(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go method definitions (functions with receivers) from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for method declarations (functions with receivers)
            query = self._language.query("""
                (method_declaration
                    receiver: (parameter_list
                        (parameter_declaration
                            type: (_) @receiver_type
                        )
                    )
                    name: (field_identifier) @method_name
                ) @method_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "method_def" not in captures or "method_name" not in captures:
                    continue

                method_node = captures["method_def"][0]
                method_name_node = captures["method_name"][0]
                method_name = self._get_node_text(method_name_node, source)

                # Get receiver type
                receiver_type = ""
                if "receiver_type" in captures:
                    receiver_type_node = captures["receiver_type"][0]
                    receiver_type = self._get_node_text(receiver_type_node, source)

                # Get full method text
                method_text = self._get_node_text(method_node, source)

                # Build qualified name with package and receiver
                qualified_name = method_name
                if receiver_type:
                    qualified_name = f"{receiver_type}.{method_name}"
                if package_name:
                    qualified_name = f"{package_name}.{qualified_name}"

                # Get method parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_types_str = ", ".join(parameters)

                # Get method return type
                return_type = self._extract_function_return_type(method_node, source)

                # Create display name
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name = f"{display_name} {return_type}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "go",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parameters": parameters,
                    "receiver_type": receiver_type,
                }

                if return_type:
                    chunk["return_type"] = return_type

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go methods: {e}")

        return chunks

    def _extract_structs(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go struct definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (type_declaration
                    (type_spec
                        name: (type_identifier) @struct_name
                        type: (struct_type) @struct_type
                    )
                ) @struct_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "struct_def" not in captures or "struct_name" not in captures:
                    continue

                struct_node = captures["struct_def"][0]
                struct_name_node = captures["struct_name"][0]
                struct_name = self._get_node_text(struct_name_node, source)

                # Get full struct text
                struct_text = self._get_node_text(struct_node, source)

                # Build qualified name with package
                qualified_name = struct_name
                if package_name:
                    qualified_name = f"{package_name}.{struct_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": struct_node.start_point[0] + 1,
                    "end_line": struct_node.end_point[0] + 1,
                    "code": struct_text,
                    "chunk_type": ChunkType.STRUCT.value,
                    "language": "go",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": struct_text,
                    "start_byte": struct_node.start_byte,
                    "end_byte": struct_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go structs: {e}")

        return chunks

    def _extract_interfaces(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go interface definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (type_declaration
                    (type_spec
                        name: (type_identifier) @interface_name
                        type: (interface_type) @interface_type
                    )
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

                # Get full interface text
                interface_text = self._get_node_text(interface_node, source)

                # Build qualified name with package
                qualified_name = interface_name
                if package_name:
                    qualified_name = f"{package_name}.{interface_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": interface_node.start_point[0] + 1,
                    "end_line": interface_node.end_point[0] + 1,
                    "code": interface_text,
                    "chunk_type": ChunkType.INTERFACE.value,
                    "language": "go",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": interface_text,
                    "start_byte": interface_node.start_byte,
                    "end_byte": interface_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go interfaces: {e}")

        return chunks

    def _extract_types(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go type declarations (type aliases) from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for type aliases (not structs or interfaces)
            query = self._language.query("""
                (type_declaration
                    (type_spec
                        name: (type_identifier) @type_name
                        type: (_) @type_def
                    )
                ) @full_type_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if (
                    "full_type_def" not in captures
                    or "type_name" not in captures
                    or "type_def" not in captures
                ):
                    continue

                full_node = captures["full_type_def"][0]
                type_name_node = captures["type_name"][0]
                type_def_node = captures["type_def"][0]

                # Skip structs and interfaces (handled separately)
                if type_def_node.type in ["struct_type", "interface_type"]:
                    continue

                type_name = self._get_node_text(type_name_node, source)

                # Get full type text
                type_text = self._get_node_text(full_node, source)

                # Build qualified name with package
                qualified_name = type_name
                if package_name:
                    qualified_name = f"{package_name}.{type_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": full_node.start_point[0] + 1,
                    "end_line": full_node.end_point[0] + 1,
                    "code": type_text,
                    "chunk_type": ChunkType.TYPE.value,
                    "language": "go",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": type_text,
                    "start_byte": full_node.start_byte,
                    "end_byte": full_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go types: {e}")

        return chunks

    def _extract_variables(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Go variable and constant declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for var and const declarations
            query = self._language.query("""
                (var_declaration) @var_def
                (const_declaration) @const_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                var_node = None

                # Handle variable declarations
                if "var_def" in captures:
                    var_node = captures["var_def"][0]

                # Handle constant declarations
                elif "const_def" in captures:
                    var_node = captures["const_def"][0]

                if not var_node:
                    continue

                # Get full declaration text
                var_text = self._get_node_text(var_node, source)

                # Extract individual variable/constant names from the declaration
                # This handles both single declarations and block declarations
                var_names = self._extract_variable_names(var_node, source)

                for var_name in var_names:
                    # Build qualified name with package
                    qualified_name = var_name
                    if package_name:
                        qualified_name = f"{package_name}.{var_name}"

                    # Create chunk for each variable/constant
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": var_node.start_point[0] + 1,
                        "end_line": var_node.end_point[0] + 1,
                        "code": var_text,
                        "chunk_type": ChunkType.VARIABLE.value,
                        "language": "go",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": var_text,
                        "start_byte": var_node.start_byte,
                        "end_byte": var_node.end_byte,
                    }

                    chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Go variables: {e}")

        return chunks

    def _extract_function_parameters(self, func_node: TSNode, source: str) -> list[str]:
        """Extract parameter types from a Go function."""
        parameters = []

        try:
            if self._language is None:
                return parameters

            # Find the parameters node
            params_node = None
            for i in range(func_node.child_count):
                child = func_node.child(i)
                if child and child.type == "parameter_list":
                    params_node = child
                    break

            if not params_node:
                return parameters

            # Extract each parameter
            for i in range(params_node.child_count):
                child = params_node.child(i)
                if child and child.type == "parameter_declaration":
                    # Get parameter type
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        param_type = self._get_node_text(type_node, source).strip()
                        parameters.append(param_type)

        except Exception as e:
            logger.error(f"Failed to extract Go function parameters: {e}")

        return parameters

    def _extract_function_return_type(
        self, func_node: TSNode, source: str
    ) -> str | None:
        """Extract return type from a Go function."""
        try:
            if self._language is None:
                return None

            # Find the result/return type node
            result_node = func_node.child_by_field_name("result")
            if result_node:
                return self._get_node_text(result_node, source).strip()
            return None
        except Exception as e:
            logger.error(f"Failed to extract Go function return type: {e}")
            return None

    def _extract_variable_names(self, var_node: TSNode, source: str) -> list[str]:
        """Extract variable names from a variable or constant declaration."""
        names = []

        try:
            if self._language is None:
                return names

            # Use tree-sitter query to find specific variable/constant identifiers
            query = self._language.query("""
                (var_spec
                    name: (identifier) @var_name
                )
                (const_spec
                    name: (identifier) @const_name
                )
            """)

            matches = query.matches(var_node)

            for match in matches:
                pattern_index, captures = match

                # Handle variable name
                if "var_name" in captures:
                    var_name_node = captures["var_name"][0]
                    var_name = self._get_node_text(var_name_node, source)
                    if var_name not in names:
                        names.append(var_name)

                # Handle constant name
                if "const_name" in captures:
                    const_name_node = captures["const_name"][0]
                    const_name = self._get_node_text(const_name_node, source)
                    if const_name not in names:
                        names.append(const_name)

        except Exception as e:
            logger.error(f"Failed to extract Go variable names: {e}")

        return names
