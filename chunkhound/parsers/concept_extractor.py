"""Universal concept extraction using language-specific mappings."""

from typing import Dict, List, Optional, Protocol, Any

from tree_sitter import Node, Tree

from .universal_engine import (
    TreeSitterEngine,
    UniversalConcept,
    UniversalChunk,
    QueryCompilationError
)


class LanguageMapping(Protocol):
    """Protocol for language-specific tree-sitter mappings."""
    
    def get_query_for_concept(self, concept: UniversalConcept) -> Optional[str]:
        """Get tree-sitter query for universal concept in this language."""
        ...
    
    def extract_name(self, concept: UniversalConcept, captures: Dict[str, Node], content: bytes) -> str:
        """Extract name from captures for this concept."""
        ...
    
    def extract_content(self, concept: UniversalConcept, captures: Dict[str, Node], content: bytes) -> str:
        """Extract content from captures for this concept."""
        ...
    
    def extract_metadata(self, concept: UniversalConcept, captures: Dict[str, Node], content: bytes) -> Dict[str, Any]:
        """Extract language-specific metadata."""
        ...


class ConceptExtractor:
    """Extracts universal concepts using language-specific mappings."""
    
    def __init__(self, engine: TreeSitterEngine, mapping: LanguageMapping):
        self.engine = engine
        self.mapping = mapping
        self._compiled_queries: Dict[UniversalConcept, Any] = {}
        self._compile_all_queries()
    
    def _compile_all_queries(self) -> None:
        """Compile all concept queries for this language - fail fast."""
        for concept in UniversalConcept:
            query_template = self.mapping.get_query_for_concept(concept)
            if query_template:
                try:
                    self._compiled_queries[concept] = self.engine.compile_query(query_template)
                except Exception as e:
                    raise QueryCompilationError(
                        concept=concept,
                        language=self.engine.language_name,
                        query=query_template,
                        error=str(e)
                    )
    
    def extract_concept(self, ast_root: Node, content: bytes, concept: UniversalConcept) -> List[UniversalChunk]:
        """Extract all instances of a universal concept."""
        if concept not in self._compiled_queries:
            return []
        
        query = self._compiled_queries[concept]
        chunks = []
        
        for match in query.matches(ast_root):
            # match is a tuple: (pattern_index, captures_dict)
            _, captures_dict = match
            # Flatten the captures dict (values are lists, take first element)
            captures = {name: nodes[0] for name, nodes in captures_dict.items() if nodes}
            chunk = self._build_universal_chunk(concept, captures, content)
            if chunk:  # Some extractions may return None
                chunks.append(chunk)
        
        return chunks
    
    def extract_all_concepts(self, ast_root: Node, content: bytes) -> List[UniversalChunk]:
        """Extract all universal concepts from the AST."""
        all_chunks = []
        for concept in UniversalConcept:
            concept_chunks = self.extract_concept(ast_root, content, concept)
            all_chunks.extend(concept_chunks)
        return all_chunks
    
    def _build_universal_chunk(self, concept: UniversalConcept, captures: Dict[str, Node], content: bytes) -> Optional[UniversalChunk]:
        """Convert language-specific captures to universal chunk."""
        # Use mapping to extract universal fields from language-specific captures
        name = self.mapping.extract_name(concept, captures, content)
        chunk_content = self.mapping.extract_content(concept, captures, content)
        metadata = self.mapping.extract_metadata(concept, captures, content)
        
        # Skip empty chunks
        if not chunk_content:
            return None
        
        # Get position from definition node
        def_node = captures.get('definition') or captures.get('node') or list(captures.values())[0] if captures else None
        if not def_node:
            return None
            
        start_line = def_node.start_point[0] + 1
        end_line = def_node.end_point[0] + 1
        
        return UniversalChunk(
            concept=concept,
            name=name,
            content=chunk_content,
            start_line=start_line,
            end_line=end_line,
            metadata=metadata,
            language_node_type=def_node.type
        )