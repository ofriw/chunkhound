"""Makefile language parser provider implementation for ChunkHound using tree-sitter."""

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

# Try direct import as fallback
try:
    import tree_sitter_make

    MAKE_DIRECT_AVAILABLE = True
except ImportError:
    MAKE_DIRECT_AVAILABLE = False
    tree_sitter_make = None


class MakefileParser(TreeSitterParserBase):
    """Makefile language parser using tree-sitter."""

    def __init__(self, config: ParseConfig | None = None):
        """Initialize Makefile parser.

        Args:
            config: Optional parse configuration
        """
        super().__init__(CoreLanguage.MAKEFILE, config)

    def _get_default_config(self) -> ParseConfig:
        """Get default configuration for Makefile parser."""
        return ParseConfig(
            language=CoreLanguage.MAKEFILE,
            chunk_types={ChunkType.FUNCTION, ChunkType.BLOCK, ChunkType.COMMENT},
            max_chunk_size=8000,
            min_chunk_size=50,
            include_imports=True,
            include_comments=True,
            include_docstrings=False,
            max_depth=10,
            use_cache=True,
        )

    def _get_tree_sitter_language_name(self) -> str:
        """Get tree-sitter language name for Makefile."""
        return "make"

    def _initialize(self) -> bool:
        """Initialize the Makefile parser using language pack pattern with fallback.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        if not TREE_SITTER_AVAILABLE and not MAKE_DIRECT_AVAILABLE:
            logger.error("Makefile tree-sitter support not available")
            return False

        # Try language pack first
        try:
            if TREE_SITTER_AVAILABLE and get_language and get_parser:
                self._language = get_language("make")
                self._parser = get_parser("make")
                self._initialized = True
                logger.debug("Makefile parser initialized successfully (language pack)")
                return True
        except Exception as e:
            logger.debug(f"Language pack Makefile parser initialization failed: {e}")

        # Fallback to direct import
        try:
            if MAKE_DIRECT_AVAILABLE and tree_sitter_make and TSLanguage and TSParser:
                self._language = TSLanguage(tree_sitter_make.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Makefile parser initialized successfully (direct)")
                return True
        except Exception as e:
            logger.error(f"Direct Makefile parser initialization failed: {e}")

        logger.error("Makefile parser initialization failed with both methods")
        return False

    def _extract_chunks(
        self, tree_node: TSNode, source: str, file_path: Path
    ) -> list[dict[str, Any]]:
        """Extract semantic chunks from Makefile AST.

        Args:
            tree_node: Root AST node
            source: Source code string
            file_path: Path to source file

        Returns:
            List of extracted chunks
        """
        chunks = []
        source_lines = source.split("\n")

        self._extract_makefile_constructs(
            tree_node, source, source_lines, file_path, chunks
        )

        return chunks

    def _extract_makefile_constructs(
        self,
        node: TSNode,
        source: str,
        source_lines: list[str],
        file_path: Path,
        chunks: list[dict[str, Any]],
        parent: str = None,
    ) -> None:
        """Extract Makefile constructs (targets, variables, rules)."""
        if not node:
            return

        node_type = node.type

        # Extract targets (rules)
        if node_type == "rule":
            self._extract_rule(node, source, file_path, chunks, parent)

        # Extract variable definitions
        elif node_type in ["variable_assignment", "define_directive"]:
            self._extract_variable(node, source, file_path, chunks, parent)

        # Extract comments
        elif node_type == "comment" and self._config.include_comments:
            self._extract_comment(node, source, file_path, chunks, parent)

        # Recursively process child nodes
        for child in node.children:
            self._extract_makefile_constructs(
                child, source, source_lines, file_path, chunks, parent
            )

    def _extract_rule(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunks: list[dict[str, Any]],
        parent: str = None,
    ) -> None:
        """Extract rule/target definition."""
        try:
            # Find the target name (first child is usually the targets)
            target_node = None
            recipe_node = None

            for child in node.children:
                if child.type == "targets":
                    target_node = child
                elif child.type == "recipe":
                    recipe_node = child

            if target_node:
                target_text = self._get_node_text(target_node, source).strip()
                # Take the first target if multiple
                target_name = target_text.split()[0] if target_text else "unknown"

                # Create chunk for the entire rule
                chunk = self._create_chunk(
                    node,
                    source,
                    file_path,
                    ChunkType.FUNCTION,
                    target_name,
                    display_name=f"target {target_name}",
                    parent=parent,
                    rule_type="target",
                    targets=target_text,
                )
                chunks.append(chunk)

                # If there's a recipe, create a separate chunk for it
                if recipe_node:
                    recipe_text = self._get_node_text(recipe_node, source).strip()
                    if recipe_text:
                        recipe_chunk = self._create_chunk(
                            recipe_node,
                            source,
                            file_path,
                            ChunkType.BLOCK,
                            f"{target_name}_recipe",
                            display_name=f"{target_name} recipe",
                            parent=target_name,
                            rule_type="recipe",
                        )
                        chunks.append(recipe_chunk)

        except Exception as e:
            logger.debug(f"Error extracting rule: {e}")

    def _extract_variable(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunks: list[dict[str, Any]],
        parent: str = None,
    ) -> None:
        """Extract variable definition."""
        try:
            node_text = self._get_node_text(node, source)

            # Extract variable name
            var_name = "unknown"
            if node.type == "variable_assignment":
                # Try to find the variable name (usually first child or by looking for = sign)
                if node.children:
                    name_node = node.children[0]
                    var_name = self._get_node_text(name_node, source).strip()
            elif node.type == "define_directive":
                # For define directives, variable name is after 'define'
                lines = node_text.split("\n")
                if lines:
                    first_line = lines[0].strip()
                    if first_line.startswith("define"):
                        var_name = first_line[6:].strip()

            chunk = self._create_chunk(
                node,
                source,
                file_path,
                ChunkType.FIELD,
                var_name,
                display_name=f"variable {var_name}",
                parent=parent,
                variable_type="assignment"
                if node.type == "variable_assignment"
                else "define",
            )
            chunks.append(chunk)

        except Exception as e:
            logger.debug(f"Error extracting variable: {e}")

    def _extract_comment(
        self,
        node: TSNode,
        source: str,
        file_path: Path,
        chunks: list[dict[str, Any]],
        parent: str = None,
    ) -> None:
        """Extract comment."""
        try:
            comment_text = self._get_node_text(node, source).strip()

            # Only extract meaningful comments (not just single # lines)
            if len(comment_text) > 10:
                chunk = self._create_chunk(
                    node,
                    source,
                    file_path,
                    ChunkType.COMMENT,
                    f"comment_{node.start_point[0]}",
                    display_name="comment",
                    parent=parent,
                    comment_type="inline",
                )
                chunks.append(chunk)

        except Exception as e:
            logger.debug(f"Error extracting comment: {e}")
