"""Haskell language mapping for the unified parser architecture.

This mapping extracts semantic concepts from Haskell source using the
Tree-sitter grammar. It leverages the base mapping adapter so function
definitions, data/newtype declarations, type synonyms, and type classes can be
fed into the universal ConceptExtractor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from chunkhound.core.types.common import Language
from chunkhound.parsers.mappings.base import BaseMapping

if TYPE_CHECKING:
    from tree_sitter import Node as TSNode

try:
    from tree_sitter import Node as TSNode

    TREE_SITTER_AVAILABLE = True
except ImportError:  # pragma: no cover - handled in runtime environments
    TREE_SITTER_AVAILABLE = False
    TSNode = Any  # type: ignore


class HaskellMapping(BaseMapping):
    """Haskell-specific mapping implementation."""

    def __init__(self) -> None:
        super().__init__(Language.HASKELL)

    # BaseMapping abstract methods -------------------------------------------------
    def get_function_query(self) -> str:
        """Capture top-level function bindings."""
        return """
            (function
                name: (_) @function_name
            ) @function_def

            (bind
                name: (_) @function_name
            ) @function_def

            (pattern_synonym
                (signature
                    synonym: (_) @function_name
                )
            ) @function_def

            (pattern_synonym
                (equation
                    synonym: (_) @function_name
                )
            ) @function_def
        """

    def get_class_query(self) -> str:
        """Capture algebraic data types, newtypes, type synonyms, and type classes."""
        return """
            (data_type
                name: (_) @class_name
            ) @class_def

            (newtype
                name: (_) @class_name
            ) @class_def

            (type_synomym
                name: (_) @class_name
            ) @class_def

            (type_family
                name: (_) @class_name
            ) @class_def

            (data_family
                name: (_) @class_name
            ) @class_def

            (instance
                name: (_) @class_name
            ) @class_def

            (class
                name: (_) @class_name
            ) @class_def
        """

    def get_method_query(self) -> str:
        """Capture methods defined inside type classes."""
        return """
            (class
                declarations: (class_declarations
                    (function
                        name: (_) @method_name
                    ) @method_def
                )
            )
        """

    def get_comment_query(self) -> str:
        """Capture line, block, and Haddock comments."""
        return """
            (comment) @comment
            (haddock) @comment
        """

    def extract_function_name(self, node: TSNode | None, source: str) -> str:
        """Extract the bound function name, falling back when necessary."""
        if not TREE_SITTER_AVAILABLE or node is None:
            return self.get_fallback_name(node, "function")

        # Functions and binds expose 'name'; pattern synonyms expose 'synonym'
        name_node = node.child_by_field_name("name")
        if name_node is None and node.type == "pattern_synonym":
            name_node = node.child_by_field_name("synonym")
        if name_node is None and node.child_count > 0:
            name_node = node.child(0)

        if name_node is not None:
            text = self.get_node_text(name_node, source).strip()
            if text:
                return text

        return self.get_fallback_name(node, "function")

    def extract_class_name(self, node: TSNode | None, source: str) -> str:
        """Extract the declared type name for data/newtype/class/type synonym."""
        if not TREE_SITTER_AVAILABLE or node is None:
            return self.get_fallback_name(node, "type")

        name_node = node.child_by_field_name("name")
        if name_node is None and node.child_count > 0:
            name_node = node.child(0)

        text = ""
        if name_node is not None:
            text = self.get_node_text(name_node, source).strip()

        if node.type == "instance":
            type_patterns = node.child_by_field_name("type_patterns")
            if type_patterns is not None:
                patterns_text = self.get_node_text(type_patterns, source).strip()
                if patterns_text:
                    text = f"{text} {patterns_text}".strip()
        else:
            param_field = node.child_by_field_name("type_params") or node.child_by_field_name(
                "patterns"
            )
            if param_field is not None:
                params_text = self.get_node_text(param_field, source).strip()
                if params_text:
                    text = f"{text} {params_text}".strip()

        if text:
            return text

        return self.get_fallback_name(node, "type")

    # Optional overrides -----------------------------------------------------------
    # Uses BaseMapping default filtering behaviour.
