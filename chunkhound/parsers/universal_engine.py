"""Universal tree-sitter parsing engine for all languages."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from tree_sitter import Language, Node, Parser, Query, Tree


class UniversalConcept(Enum):
    """Universal semantic concepts found in ALL programming languages."""

    DEFINITION = "definition"  # Functions, classes, types, variables
    BLOCK = "block"  # Scoped regions, logical groupings
    COMMENT = "comment"  # Documentation, explanations
    IMPORT = "import"  # Dependencies, includes, modules
    STRUCTURE = "structure"  # Hierarchical organization (headers, sections)


@dataclass(frozen=True)
class UniversalChunk:
    """Language-agnostic representation of semantic code unit."""

    concept: UniversalConcept
    name: str
    content: str
    start_line: int
    end_line: int
    metadata: dict[str, Any]
    language_node_type: str  # Original tree-sitter type for debugging


@dataclass(frozen=True)
class SetupError(Exception):
    """Error raised when parser setup fails."""

    parser: str
    missing_dependency: str
    install_command: str
    original_error: str

    def __str__(self) -> str:
        return (
            f"Parser {self.parser} setup failed:\n"
            f"Missing: {self.missing_dependency}\n"
            f"Fix: {self.install_command}\n"
            f"Details: {self.original_error}"
        )


@dataclass(frozen=True)
class QueryCompilationError(Exception):
    """Error raised when tree-sitter query compilation fails."""

    concept: UniversalConcept
    language: str
    query: str
    error: str

    def __str__(self) -> str:
        return (
            f"Query compilation failed for {self.concept} in {self.language}:\n"
            f"Query: {self.query}\n"
            f"Error: {self.error}"
        )


class TreeSitterEngine:
    """Universal tree-sitter parsing engine - works for ALL languages."""

    def __init__(self, language_name: str, tree_sitter_language: Language):
        """Initialize with pre-imported tree-sitter language object.

        Args:
            language_name: Name of the language (e.g., 'python', 'javascript')
            tree_sitter_language: Tree-sitter Language object for this language
        """
        self.language_name = language_name
        self._language = tree_sitter_language
        self._parser = Parser()
        self._parser.language = self._language

    def parse_to_ast(self, content: str) -> Tree:
        """Parse content to AST - universal across all languages."""
        return self._parser.parse(content.encode("utf-8"))

    def compile_query(self, query_string: str) -> Query:
        """Compile tree-sitter query - universal syntax."""
        try:
            return Query(self._language, query_string)
        except Exception as e:
            # Re-raise with more context
            raise QueryCompilationError(
                concept=UniversalConcept.DEFINITION,  # Will be overridden by caller
                language=self.language_name,
                query=query_string,
                error=str(e),
            )

    def get_node_text(self, node: Node, content: bytes) -> str:
        """Get text content of a node."""
        return content[node.start_byte : node.end_byte].decode("utf-8")
