"""Rust language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

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

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None

# Try direct import as fallback
try:
    import tree_sitter_rust as ts_rust

    RUST_DIRECT_AVAILABLE = True
except ImportError:
    RUST_DIRECT_AVAILABLE = False
    ts_rust = None


class RustParser:
    """Rust language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Rust parser.

        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False

        # Default configuration for Rust-specific chunk types
        self._config = config or ParseConfig(
            language=CoreLanguage.RUST,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.METHOD,
                ChunkType.STRUCT,
                ChunkType.ENUM,
                ChunkType.TRAIT,
                ChunkType.INTERFACE,  # For trait implementations
                ChunkType.NAMESPACE,  # For modules
                ChunkType.MACRO,
                ChunkType.VARIABLE,  # Constants and statics
                ChunkType.TYPE,  # Type aliases
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
        if not RUST_AVAILABLE and not RUST_DIRECT_AVAILABLE:
            raise ImportError(
                "Rust tree-sitter dependencies not available - install tree-sitter-language-pack or tree-sitter-rust"
            )

        if not self._initialize():
            raise RuntimeError("Failed to initialize Rust parser")

    def _initialize(self) -> bool:
        """Initialize the Rust parser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not RUST_AVAILABLE and not RUST_DIRECT_AVAILABLE:
            logger.error("Rust tree-sitter support not available")
            return False

        # Try direct import first
        try:
            if RUST_DIRECT_AVAILABLE and ts_rust and TSLanguage and TSParser:
                self._language = TSLanguage(ts_rust.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Rust parser initialized successfully (direct)")
                return True
        except Exception as e:
            logger.debug(f"Direct Rust parser initialization failed: {e}")

        # Fallback to language pack
        try:
            if RUST_AVAILABLE and get_language and get_parser:
                self._language = get_language("rust")
                self._parser = get_parser("rust")
                self._initialized = True
                logger.debug("Rust parser initialized successfully (language pack)")
                return True
        except Exception as e:
            logger.error(f"Rust parser language pack initialization failed: {e}")

        logger.error("Rust parser initialization failed with both methods")
        return False

    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.RUST

    @property
    def supported_chunk_types(self) -> set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types

    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return (RUST_AVAILABLE or RUST_DIRECT_AVAILABLE) and self._initialized

    def parse_file(self, file_path: Path, source: str | None = None) -> ParseResult:
        """Parse a Rust file and extract semantic chunks.

        Args:
            file_path: Path to Rust file
            source: Optional source code string

        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []

        if not self.is_available:
            errors.append("Rust parser not available")
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
                errors.append("Rust parser not initialized")
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

            # Extract module path for context
            module_path = (
                self._extract_module_path(tree.root_node, source, file_path)
                if tree
                else ""
            )

            # Extract semantic units
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(
                    self._extract_functions(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.METHOD in self._config.chunk_types:
                chunks.extend(
                    self._extract_methods(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.STRUCT in self._config.chunk_types:
                chunks.extend(
                    self._extract_structs(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(
                    self._extract_enums(tree.root_node, source, file_path, module_path)
                )

            if ChunkType.TRAIT in self._config.chunk_types:
                chunks.extend(
                    self._extract_traits(tree.root_node, source, file_path, module_path)
                )

            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(
                    self._extract_implementations(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.NAMESPACE in self._config.chunk_types:
                chunks.extend(
                    self._extract_modules(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.MACRO in self._config.chunk_types:
                chunks.extend(
                    self._extract_macros(tree.root_node, source, file_path, module_path)
                )

            if ChunkType.VARIABLE in self._config.chunk_types:
                chunks.extend(
                    self._extract_variables(
                        tree.root_node, source, file_path, module_path
                    )
                )

            if ChunkType.TYPE in self._config.chunk_types:
                chunks.extend(
                    self._extract_types(tree.root_node, source, file_path, module_path)
                )

            # Extract comments and docstrings
            if ChunkType.COMMENT in self._config.chunk_types:
                chunks.extend(self._extract_comments(tree.root_node, source, file_path))

            if ChunkType.DOCSTRING in self._config.chunk_types:
                chunks.extend(
                    self._extract_docstrings(tree.root_node, source, file_path)
                )

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")

        except Exception as e:
            error_msg = f"Failed to parse Rust file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            module_path = ""  # Set default value on error

        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={
                "file_path": str(file_path),
                "module_path": module_path if "module_path" in locals() else "",
            },
        )

    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte : node.end_byte]

    def _extract_module_path(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> str:
        """Extract module path from Rust file context.

        Args:
            tree_node: Root node of the Rust AST
            source: Source code content
            file_path: Path to the Rust file

        Returns:
            Module path as string
        """
        # For now, use the file path as module context
        # This could be enhanced to parse actual module declarations
        return file_path.stem

    def _extract_functions(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust function definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for function declarations (not associated methods)
            query = self._language.query("""
                (function_item
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

                # Build qualified name with module
                qualified_name = func_name
                if module_path:
                    qualified_name = f"{module_path}::{func_name}"

                # Get function parameters
                parameters = self._extract_function_parameters(func_node, source)
                param_types_str = ", ".join(parameters)

                # Get function return type
                return_type = self._extract_function_return_type(func_node, source)

                # Create display name
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name = f"{display_name} -> {return_type}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": func_node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "code": func_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "rust",
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
            logger.error(f"Failed to extract Rust functions: {e}")

        return chunks

    def _extract_methods(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust method definitions (impl block methods) from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for method declarations in impl blocks
            query = self._language.query("""
                (impl_item
                    type: (_) @impl_type
                    body: (declaration_list
                        (function_item
                            name: (identifier) @method_name
                        ) @method_def
                    )
                )
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "method_def" not in captures or "method_name" not in captures:
                    continue

                method_node = captures["method_def"][0]
                method_name_node = captures["method_name"][0]
                method_name = self._get_node_text(method_name_node, source)

                # Get impl type if available
                impl_type = ""
                if "impl_type" in captures:
                    impl_type_node = captures["impl_type"][0]
                    impl_type = self._get_node_text(impl_type_node, source)

                # Get full method text
                method_text = self._get_node_text(method_node, source)

                # Build qualified name with module and impl type
                qualified_name = method_name
                if impl_type:
                    qualified_name = f"{impl_type}::{method_name}"
                if module_path:
                    qualified_name = f"{module_path}::{qualified_name}"

                # Get method parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_types_str = ", ".join(parameters)

                # Get method return type
                return_type = self._extract_function_return_type(method_node, source)

                # Create display name
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name = f"{display_name} -> {return_type}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parameters": parameters,
                    "impl_type": impl_type,
                }

                if return_type:
                    chunk["return_type"] = return_type

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust methods: {e}")

        return chunks

    def _extract_structs(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust struct definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (struct_item
                    name: (type_identifier) @struct_name
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

                # Build qualified name with module
                qualified_name = struct_name
                if module_path:
                    qualified_name = f"{module_path}::{struct_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": struct_node.start_point[0] + 1,
                    "end_line": struct_node.end_point[0] + 1,
                    "code": struct_text,
                    "chunk_type": ChunkType.STRUCT.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": struct_text,
                    "start_byte": struct_node.start_byte,
                    "end_byte": struct_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust structs: {e}")

        return chunks

    def _extract_enums(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust enum definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (enum_item
                    name: (type_identifier) @enum_name
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

                # Get full enum text
                enum_text = self._get_node_text(enum_node, source)

                # Build qualified name with module
                qualified_name = enum_name
                if module_path:
                    qualified_name = f"{module_path}::{enum_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": enum_node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "code": enum_text,
                    "chunk_type": ChunkType.ENUM.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": enum_text,
                    "start_byte": enum_node.start_byte,
                    "end_byte": enum_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust enums: {e}")

        return chunks

    def _extract_traits(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust trait definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (trait_item
                    name: (type_identifier) @trait_name
                ) @trait_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "trait_def" not in captures or "trait_name" not in captures:
                    continue

                trait_node = captures["trait_def"][0]
                trait_name_node = captures["trait_name"][0]
                trait_name = self._get_node_text(trait_name_node, source)

                # Get full trait text
                trait_text = self._get_node_text(trait_node, source)

                # Build qualified name with module
                qualified_name = trait_name
                if module_path:
                    qualified_name = f"{module_path}::{trait_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": trait_node.start_point[0] + 1,
                    "end_line": trait_node.end_point[0] + 1,
                    "code": trait_text,
                    "chunk_type": ChunkType.TRAIT.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": trait_text,
                    "start_byte": trait_node.start_byte,
                    "end_byte": trait_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust traits: {e}")

        return chunks

    def _extract_implementations(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust impl block definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (impl_item
                    type: (_) @impl_type
                    trait: (_)? @trait_type
                ) @impl_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "impl_def" not in captures or "impl_type" not in captures:
                    continue

                impl_node = captures["impl_def"][0]
                impl_type_node = captures["impl_type"][0]
                impl_type = self._get_node_text(impl_type_node, source)

                # Check if this is a trait implementation
                trait_name = ""
                if "trait_type" in captures:
                    trait_type_node = captures["trait_type"][0]
                    trait_name = self._get_node_text(trait_type_node, source)

                # Get full impl text
                impl_text = self._get_node_text(impl_node, source)

                # Build qualified name with module
                if trait_name:
                    qualified_name = f"{trait_name} for {impl_type}"
                else:
                    qualified_name = f"impl {impl_type}"

                if module_path:
                    qualified_name = f"{module_path}::{qualified_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": impl_node.start_point[0] + 1,
                    "end_line": impl_node.end_point[0] + 1,
                    "code": impl_text,
                    "chunk_type": ChunkType.INTERFACE.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": impl_text,
                    "start_byte": impl_node.start_byte,
                    "end_byte": impl_node.end_byte,
                    "impl_type": impl_type,
                }

                if trait_name:
                    chunk["trait_name"] = trait_name

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust implementations: {e}")

        return chunks

    def _extract_modules(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust module declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (mod_item
                    name: (identifier) @mod_name
                ) @mod_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "mod_def" not in captures or "mod_name" not in captures:
                    continue

                mod_node = captures["mod_def"][0]
                mod_name_node = captures["mod_name"][0]
                mod_name = self._get_node_text(mod_name_node, source)

                # Get full module text
                mod_text = self._get_node_text(mod_node, source)

                # Build qualified name with parent module
                qualified_name = mod_name
                if module_path:
                    qualified_name = f"{module_path}::{mod_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": mod_node.start_point[0] + 1,
                    "end_line": mod_node.end_point[0] + 1,
                    "code": mod_text,
                    "chunk_type": ChunkType.NAMESPACE.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": mod_text,
                    "start_byte": mod_node.start_byte,
                    "end_byte": mod_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust modules: {e}")

        return chunks

    def _extract_macros(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust macro definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (macro_definition
                    name: (identifier) @macro_name
                ) @macro_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                if "macro_def" not in captures or "macro_name" not in captures:
                    continue

                macro_node = captures["macro_def"][0]
                macro_name_node = captures["macro_name"][0]
                macro_name = self._get_node_text(macro_name_node, source)

                # Get full macro text
                macro_text = self._get_node_text(macro_node, source)

                # Build qualified name with module
                qualified_name = f"{macro_name}!"
                if module_path:
                    qualified_name = f"{module_path}::{qualified_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": macro_node.start_point[0] + 1,
                    "end_line": macro_node.end_point[0] + 1,
                    "code": macro_text,
                    "chunk_type": ChunkType.MACRO.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": macro_text,
                    "start_byte": macro_node.start_byte,
                    "end_byte": macro_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust macros: {e}")

        return chunks

    def _extract_variables(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust const and static declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for const and static declarations
            query = self._language.query("""
                (const_item
                    name: (identifier) @const_name
                ) @const_def
                (static_item
                    name: (identifier) @static_name
                ) @static_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                var_node = None
                var_name = None

                # Handle const declarations
                if "const_def" in captures and "const_name" in captures:
                    var_node = captures["const_def"][0]
                    var_name_node = captures["const_name"][0]
                    var_name = self._get_node_text(var_name_node, source)

                # Handle static declarations
                elif "static_def" in captures and "static_name" in captures:
                    var_node = captures["static_def"][0]
                    var_name_node = captures["static_name"][0]
                    var_name = self._get_node_text(var_name_node, source)

                if not var_node or not var_name:
                    continue

                # Get full declaration text
                var_text = self._get_node_text(var_node, source)

                # Build qualified name with module
                qualified_name = var_name
                if module_path:
                    qualified_name = f"{module_path}::{var_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": var_node.start_point[0] + 1,
                    "end_line": var_node.end_point[0] + 1,
                    "code": var_text,
                    "chunk_type": ChunkType.VARIABLE.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": var_text,
                    "start_byte": var_node.start_byte,
                    "end_byte": var_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust variables: {e}")

        return chunks

    def _extract_types(
        self, tree_node: TSNode, source: str, file_path: Path, module_path: str
    ) -> list[dict[str, Any]]:
        """Extract Rust type alias declarations from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (type_item
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

                # Get full type text
                type_text = self._get_node_text(type_node, source)

                # Build qualified name with module
                qualified_name = type_name
                if module_path:
                    qualified_name = f"{module_path}::{type_name}"

                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": type_node.start_point[0] + 1,
                    "end_line": type_node.end_point[0] + 1,
                    "code": type_text,
                    "chunk_type": ChunkType.TYPE.value,
                    "language": "rust",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": type_text,
                    "start_byte": type_node.start_byte,
                    "end_byte": type_node.end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust types: {e}")

        return chunks

    def _extract_function_parameters(self, func_node: TSNode, source: str) -> list[str]:
        """Extract parameter types from a Rust function."""
        parameters = []

        try:
            if self._language is None:
                return parameters

            # Find the parameters node
            params_node = None
            for i in range(func_node.child_count):
                child = func_node.child(i)
                if child and child.type == "parameters":
                    params_node = child
                    break

            if not params_node:
                return parameters

            # Extract each parameter
            for i in range(params_node.child_count):
                child = params_node.child(i)
                if child and child.type == "parameter":
                    # Get parameter type
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        param_type = self._get_node_text(type_node, source).strip()
                        parameters.append(param_type)

        except Exception as e:
            logger.error(f"Failed to extract Rust function parameters: {e}")

        return parameters

    def _extract_function_return_type(
        self, func_node: TSNode, source: str
    ) -> str | None:
        """Extract return type from a Rust function."""
        try:
            if self._language is None:
                return None

            # Find the return type node
            return_type_node = func_node.child_by_field_name("return_type")
            if return_type_node:
                # Skip the "->" token and get the actual type
                for i in range(return_type_node.child_count):
                    child = return_type_node.child(i)
                    if child and child.type != "->":
                        return self._get_node_text(child, source).strip()
            return None
        except Exception as e:
            logger.error(f"Failed to extract Rust function return type: {e}")
            return None

    def _extract_comments(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Rust comments (//)."""
        comment_patterns = ["(line_comment) @comment", "(block_comment) @comment"]
        return self._extract_comments_generic(
            tree_node, source, file_path, comment_patterns
        )

    def _extract_docstrings(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract Rust documentation comments (/// and /** */)."""
        chunks = []

        if self._language is None:
            return chunks

        try:
            # Extract documentation comments (/// and /** ... */)
            query = self._language.query("""
                (line_comment) @doc_comment
                (block_comment) @doc_comment
            """)
            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match

                for capture_name, nodes in captures.items():
                    for node in nodes:
                        comment_text = self._get_node_text(node, source)

                        # Check if it's a documentation comment (starts with /// or /** or //!)
                        if (
                            comment_text.strip().startswith("///")
                            or comment_text.strip().startswith("//!")
                            or comment_text.strip().startswith("/*!")
                            or comment_text.strip().startswith("/**")
                        ):
                            cleaned_text = self._clean_rust_doc_text(comment_text)
                            symbol = f"doc:{node.start_point[0] + 1}"

                            chunk = self._create_chunk(
                                node=node,
                                source=source,
                                file_path=file_path,
                                chunk_type=ChunkType.DOCSTRING,
                                name=symbol,
                                display_name=f"Documentation at line {node.start_point[0] + 1}",
                                content=cleaned_text,
                            )

                            chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Rust docstrings: {e}")

        return chunks

    def _clean_rust_doc_text(self, text: str) -> str:
        """Clean Rust documentation comment text by removing markers and prefixes."""
        cleaned = text.strip()

        # Remove /** */ or /*! */ markers
        if (
            cleaned.startswith("/**") or cleaned.startswith("/*!")
        ) and cleaned.endswith("*/"):
            cleaned = cleaned[3:-2]
        # Remove /// or //! markers
        elif cleaned.startswith("///") or cleaned.startswith("//!"):
            lines = cleaned.split("\n")
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("///"):
                    line = line[3:].lstrip()
                elif line.startswith("//!"):
                    line = line[3:].lstrip()
                cleaned_lines.append(line)
            return "\n".join(cleaned_lines).strip()

        # Remove leading * from each line for block comments
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

                            # Skip empty comments and doc comments (handled separately)
                            if (
                                not comment_text.strip()
                                or comment_text.strip().startswith("///")
                                or comment_text.strip().startswith("//!")
                                or comment_text.strip().startswith("/*!")
                                or comment_text.strip().startswith("/**")
                            ):
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
            logger.error(f"Failed to extract comments for Rust: {e}")

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
            and not cleaned.startswith("/*!")
        ):
            cleaned = cleaned[2:-2].strip()

        return cleaned

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
        """Create a standard chunk dictionary."""
        code = self._get_node_text(node, source)

        chunk = {
            "symbol": name,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "code": code,
            "chunk_type": chunk_type.value,
            "language": "rust",
            "path": str(file_path),
            "name": name,
            "display_name": display_name or name,
            "content": extra_fields.get("content", code),
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }

        if parent:
            chunk["parent"] = parent

        # Add extra fields
        for key, value in extra_fields.items():
            if key != "content":  # content already handled above
                chunk[key] = value

        return chunk
