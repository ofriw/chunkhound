"""Groovy language parser provider implementation for ChunkHound using tree-sitter."""

from pathlib import Path
from typing import Any

from loguru import logger

from chunkhound.core.types.common import ChunkType
from chunkhound.core.types.common import Language as CoreLanguage
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase

try:
    import tree_sitter_groovy
    from tree_sitter import Language, Parser
    from tree_sitter import Node as TSNode

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    TSNode = None
    Language = None
    Parser = None
    tree_sitter_groovy = None


class GroovyParser(TreeSitterParserBase):
    """Groovy language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Groovy parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.GROOVY, config)

    def _initialize(self) -> bool:
        """Initialize the Groovy parser using direct tree-sitter-groovy package.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not TREE_SITTER_AVAILABLE or tree_sitter_groovy is None:
            logger.error("Groovy tree-sitter support not available")
            return False

        try:
            # Use direct tree-sitter-groovy instead of language pack
            self._language = Language(tree_sitter_groovy.language())
            self._parser = Parser(self._language)
            self._initialized = True
            logger.debug("Groovy parser initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Groovy parser: {e}")
            return False

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for Groovy parser."""
        return ParseConfig(
            language=CoreLanguage.GROOVY,
            chunk_types={
                ChunkType.CLASS,
                ChunkType.INTERFACE,
                ChunkType.METHOD,
                ChunkType.CONSTRUCTOR,
                ChunkType.ENUM,
                ChunkType.FIELD,
                ChunkType.CLOSURE,
                ChunkType.TRAIT,
                ChunkType.SCRIPT,
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
        """Extract semantic chunks from Groovy AST.

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
            # Extract package name for context
            package_name = self._extract_package(tree_node, source)

            # Extract different chunk types based on configuration
            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(
                    self._extract_classes(tree_node, source, file_path, package_name)
                )

            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(
                    self._extract_interfaces(tree_node, source, file_path, package_name)
                )

            if ChunkType.TRAIT in self._config.chunk_types:
                chunks.extend(
                    self._extract_traits(tree_node, source, file_path, package_name)
                )

            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(
                    self._extract_enums(tree_node, source, file_path, package_name)
                )

            if (
                ChunkType.METHOD in self._config.chunk_types
                or ChunkType.CONSTRUCTOR in self._config.chunk_types
            ):
                chunks.extend(
                    self._extract_methods(tree_node, source, file_path, package_name)
                )

            if ChunkType.CLOSURE in self._config.chunk_types:
                chunks.extend(
                    self._extract_closures(tree_node, source, file_path, package_name)
                )

            if ChunkType.SCRIPT in self._config.chunk_types:
                chunks.extend(
                    self._extract_script_level_code(tree_node, source, file_path)
                )

            # Extract comments
            if ChunkType.COMMENT in self._config.chunk_types:
                comment_patterns = ["(comment) @comment"]
                chunks.extend(
                    self._extract_comments_generic(
                        tree_node, source, file_path, comment_patterns
                    )
                )

            # Extract Groovydoc comments as docstrings
            if ChunkType.DOCSTRING in self._config.chunk_types:
                docstring_patterns = [("(comment) @groovydoc", "groovydoc")]
                # Filter for Groovydoc-style comments only
                groovydoc_chunks = []
                for chunk in self._extract_docstrings_generic(
                    tree_node, source, file_path, docstring_patterns
                ):
                    if chunk["code"].strip().startswith("/**"):
                        groovydoc_chunks.append(chunk)
                chunks.extend(groovydoc_chunks)

        except Exception as e:
            logger.error(f"Failed to extract Groovy chunks: {e}")

        return chunks

    def _extract_package(self, tree_node: TSNode, source: str) -> str:
        """Extract package name from Groovy file.

        Args:
            tree_node: Root node of the Groovy AST
            source: Source code content

        Returns:
            Package name as string, or empty string if no package declaration found
        """
        try:
            if self._language is None:
                return ""

            # Groovy package declaration structure
            query = self._language.query("""
                (package_declaration
                    (scoped_identifier) @package_name
                ) @package_def
            """)

            matches = query.matches(tree_node)

            if not matches:
                return ""

            # Extract package name from first match
            for pattern_index, captures in matches:
                if "package_name" in captures:
                    package_node = captures["package_name"][0]
                    return self._get_node_text(package_node, source)

            return ""
        except Exception as e:
            logger.error(f"Failed to extract Groovy package: {e}")
            return ""

    def _extract_classes(
        self,
        tree_node: TSNode,
        source: str,
        file_path: Path,
        package_name: str,
    ) -> list[dict[str, Any]]:
        """Extract Groovy class definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for class declarations
            query = self._language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "class_def" not in captures or "class_name" not in captures:
                    continue

                class_node = captures["class_def"][0]
                class_name_node = captures["class_name"][0]
                class_name = self._get_node_text(class_name_node, source)

                # Build qualified name with package
                qualified_name = class_name
                if package_name:
                    qualified_name = f"{package_name}.{class_name}"

                # Create chunk using base class method
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
            logger.error(f"Failed to extract Groovy classes: {e}")

        return chunks

    def _extract_interfaces(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Groovy interface definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            query = self._language.query("""
                (interface_declaration
                    name: (identifier) @interface_name
                ) @interface_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "interface_def" not in captures or "interface_name" not in captures:
                    continue

                interface_node = captures["interface_def"][0]
                interface_name_node = captures["interface_name"][0]
                interface_name = self._get_node_text(interface_name_node, source)

                # Build qualified name with package
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
            logger.error(f"Failed to extract Groovy interfaces: {e}")

        return chunks

    def _extract_traits(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Groovy trait definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Groovy traits are class_declaration with @Trait annotation
            query = self._language.query("""
                (class_declaration
                    (modifiers) @modifiers
                    (identifier) @trait_name
                ) @trait_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                if "trait_def" not in captures or "trait_name" not in captures:
                    continue

                # Check if this is actually a trait (has @Trait annotation)
                is_trait = False
                if "modifiers" in captures:
                    modifiers_node = captures["modifiers"][0]
                    modifiers_text = self._get_node_text(modifiers_node, source)
                    if "@Trait" in modifiers_text:
                        is_trait = True

                if not is_trait:
                    continue

                trait_node = captures["trait_def"][0]
                trait_name_node = captures["trait_name"][0]
                trait_name = self._get_node_text(trait_name_node, source)

                # Build qualified name with package
                qualified_name = trait_name
                if package_name:
                    qualified_name = f"{package_name}.{trait_name}"

                chunk = self._create_chunk(
                    trait_node,
                    source,
                    file_path,
                    ChunkType.TRAIT,
                    qualified_name,
                    qualified_name,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Groovy traits: {e}")

        return chunks

    def _extract_enums(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Groovy enum definitions from AST."""
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

            for pattern_index, captures in matches:
                if "enum_def" not in captures or "enum_name" not in captures:
                    continue

                enum_node = captures["enum_def"][0]
                enum_name_node = captures["enum_name"][0]
                enum_name = self._get_node_text(enum_name_node, source)

                # Build qualified name with package
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
            logger.error(f"Failed to extract Groovy enums: {e}")

        return chunks

    def _extract_methods(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Groovy method definitions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for methods and constructors within classes
            query = self._language.query("""
                (method_declaration
                    name: (identifier) @method_name
                ) @method_def

                (constructor_declaration
                    name: (identifier) @constructor_name
                ) @constructor_def
            """)

            matches = query.matches(tree_node)

            for pattern_index, captures in matches:
                method_node = None
                method_name = None
                is_constructor = False

                # Handle regular methods
                if "method_def" in captures and "method_name" in captures:
                    method_node = captures["method_def"][0]
                    method_name_node = captures["method_name"][0]
                    method_name = self._get_node_text(method_name_node, source)
                    is_constructor = False

                # Handle constructors
                elif "constructor_def" in captures and "constructor_name" in captures:
                    method_node = captures["constructor_def"][0]
                    constructor_name_node = captures["constructor_name"][0]
                    method_name = self._get_node_text(constructor_name_node, source)
                    is_constructor = True

                if not method_node or not method_name:
                    continue

                # Skip if we don't want this chunk type
                if (
                    is_constructor
                    and ChunkType.CONSTRUCTOR not in self._config.chunk_types
                ):
                    continue
                if (
                    not is_constructor
                    and ChunkType.METHOD not in self._config.chunk_types
                ):
                    continue

                # Find the containing class
                parent_class = self._find_containing_class(method_node, source)

                # Build qualified name
                if parent_class and package_name:
                    qualified_name = f"{package_name}.{parent_class}.{method_name}"
                elif parent_class:
                    qualified_name = f"{parent_class}.{method_name}"
                else:
                    qualified_name = method_name

                chunk_type = (
                    ChunkType.CONSTRUCTOR if is_constructor else ChunkType.METHOD
                )

                chunk = self._create_chunk(
                    method_node,
                    source,
                    file_path,
                    chunk_type,
                    qualified_name,
                    qualified_name,
                    parent=parent_class if parent_class else None,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Groovy methods: {e}")

        return chunks

    def _extract_closures(
        self, tree_node: TSNode, source: str, file_path: Path, package_name: str
    ) -> list[dict[str, Any]]:
        """Extract Groovy closure expressions from AST."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Query for closure expressions (they are 'closure' nodes)
            query = self._language.query("""
                (closure) @closure_def
            """)

            matches = query.matches(tree_node)

            for i, (pattern_index, captures) in enumerate(matches):
                if "closure_def" not in captures:
                    continue

                closure_node = captures["closure_def"][0]

                # Create a name for the closure based on its position
                closure_name = f"closure_{i + 1}"

                # Find the containing context
                parent_context = self._find_containing_context(closure_node, source)

                # Build qualified name
                if parent_context and package_name:
                    qualified_name = f"{package_name}.{parent_context}.{closure_name}"
                elif parent_context:
                    qualified_name = f"{parent_context}.{closure_name}"
                else:
                    qualified_name = closure_name

                chunk = self._create_chunk(
                    closure_node,
                    source,
                    file_path,
                    ChunkType.CLOSURE,
                    qualified_name,
                    closure_name,
                    parent=parent_context if parent_context else None,
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Groovy closures: {e}")

        return chunks

    def _extract_script_level_code(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract script-level code from Groovy files."""
        chunks = []

        try:
            if self._language is None:
                return chunks

            # Look for top-level statements that aren't part of classes
            # This is common in Groovy scripts
            script_statements = []

            for i in range(tree_node.child_count):
                child = tree_node.child(i)
                if child and child.type not in [
                    "class_declaration",
                    "interface_declaration",
                    "enum_declaration",
                    "package_declaration",
                    "import_declaration",
                ]:
                    script_statements.append(child)

            if script_statements:
                # Create a single chunk for all script-level code
                start_line = script_statements[0].start_point[0] + 1
                end_line = script_statements[-1].end_point[0] + 1

                # Extract the text for all script statements
                script_code_parts = []
                for stmt in script_statements:
                    script_code_parts.append(self._get_node_text(stmt, source))

                script_code = "\n".join(script_code_parts)

                script_name = f"script_{file_path.stem}"

                chunk = {
                    "symbol": script_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": script_code,
                    "chunk_type": ChunkType.SCRIPT.value,
                    "language": "groovy",
                    "path": str(file_path),
                    "name": script_name,
                    "display_name": f"Script: {file_path.name}",
                    "content": script_code,
                    "start_byte": script_statements[0].start_byte,
                    "end_byte": script_statements[-1].end_byte,
                }

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Failed to extract Groovy script-level code: {e}")

        return chunks

    def _find_containing_class(self, node: TSNode, source: str) -> str | None:
        """Find the name of the class containing the given node."""
        current = node.parent

        while current:
            if current.type == "class_declaration":
                # Find the class name
                for i in range(current.child_count):
                    child = current.child(i)
                    if child and child.type == "identifier":
                        return self._get_node_text(child, source)
            current = current.parent

        return None

    def _find_containing_context(self, node: TSNode, source: str) -> str | None:
        """Find the containing context (class, method, etc.) for the given node."""
        current = node.parent

        while current:
            if current.type in [
                "class_declaration",
                "method_declaration",
                "constructor_declaration",
            ]:
                # Find the name
                for i in range(current.child_count):
                    child = current.child(i)
                    if child and child.type == "identifier":
                        return self._get_node_text(child, source)
            current = current.parent

        return None
