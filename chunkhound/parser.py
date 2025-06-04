"""Code parser module for ChunkHound - tree-sitter integration for Python AST parsing."""

from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    tspython = None
    Language = None
    Parser = None
    Node = None

from loguru import logger


class CodeParser:
    """Tree-sitter based code parser for extracting semantic units."""
    
    def __init__(self):
        """Initialize the code parser."""
        self.language: Optional[Language] = None
        self.parser: Optional[Parser] = None
        self._initialized = False
        
    def setup(self) -> None:
        """Set up tree-sitter parser for Python."""
        if not TREE_SITTER_AVAILABLE:
            logger.error("Tree-sitter dependencies not available")
            return
            
        logger.info("Setting up tree-sitter parser for Python")
        
        try:
            # Create Python language and parser
            self.language = Language(tspython.language())
            self.parser = Parser(self.language)
            self._initialized = True
            logger.info("Tree-sitter parser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tree-sitter parser: {e}")
            self._initialized = False
        
    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a Python file and extract semantic chunks.
        
        Args:
            file_path: Path to Python file to parse
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._initialized:
            logger.warning("Parser not initialized, attempting setup")
            self.setup()
            if not self._initialized:
                return []
        
        logger.debug(f"Parsing file: {file_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Parse with tree-sitter
            tree = self.parser.parse(bytes(source_code, 'utf8'))
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_functions(tree.root_node, source_code))
            chunks.extend(self._extract_classes(tree.root_node, source_code))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return []
        
    def _extract_functions(self, tree_node: Node, source_code: str) -> List[Dict[str, Any]]:
        """Extract function definitions from AST."""
        chunks = []
        
        # Query for function definitions
        query = self.language.query("""
            (function_definition
                name: (identifier) @func_name
            ) @func_def
        """)
        
        # Use query.matches and handle tuple format (pattern_index, captures)
        matches = query.matches(tree_node)
        logger.debug(f"Function query found {len(matches)} matches")
        
        for match in matches:
            pattern_index, captures = match
            func_node = None
            func_name = None
            
            # Get function definition node
            if "func_def" in captures:
                func_node = captures["func_def"][0]  # Take first match
                
            # Get function name
            if "func_name" in captures:
                func_name_node = captures["func_name"][0]  # Take first match
                func_name = self._get_node_text(func_name_node, source_code)
            
            if func_node and func_name:
                chunk = {
                    "symbol": func_name,
                    "start_line": func_node.start_point[0] + 1,  # Convert to 1-indexed
                    "end_line": func_node.end_point[0] + 1,
                    "code": self._get_node_text(func_node, source_code),
                    "chunk_type": "function"
                }
                chunks.append(chunk)
                logger.debug(f"Found function: {func_name} at lines {chunk['start_line']}-{chunk['end_line']}")
        
        return chunks
        
    def _extract_classes(self, tree_node: Node, source_code: str) -> List[Dict[str, Any]]:
        """Extract class definitions and methods from AST."""
        chunks = []
        
        # Query for class definitions
        class_query = self.language.query("""
            (class_definition
                name: (identifier) @class_name
            ) @class_def
        """)
        
        # Use query.matches and handle tuple format (pattern_index, captures)
        matches = class_query.matches(tree_node)
        logger.debug(f"Class query found {len(matches)} matches")
        
        for match in matches:
            pattern_index, captures = match
            class_node = None
            class_name = None
            
            # Get class definition node
            if "class_def" in captures:
                class_node = captures["class_def"][0]  # Take first match
                
            # Get class name
            if "class_name" in captures:
                class_name_node = captures["class_name"][0]  # Take first match
                class_name = self._get_node_text(class_name_node, source_code)
            
            if class_node and class_name:
                # Add class chunk
                class_chunk = {
                    "symbol": class_name,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "code": self._get_node_text(class_node, source_code),
                    "chunk_type": "class"
                }
                chunks.append(class_chunk)
                logger.debug(f"Found class: {class_name} at lines {class_chunk['start_line']}-{class_chunk['end_line']}")
                
                # Extract methods within this class
                method_chunks = self._extract_methods(class_node, source_code, class_name)
                chunks.extend(method_chunks)
        
        return chunks
    
    def _extract_methods(self, class_node: Node, source_code: str, class_name: str) -> List[Dict[str, Any]]:
        """Extract method definitions from a class."""
        chunks = []
        
        # Query for function definitions within the class
        method_query = self.language.query("""
            (function_definition
                name: (identifier) @method_name
            ) @method_def
        """)
        
        # Use query.matches and handle tuple format (pattern_index, captures)
        matches = method_query.matches(class_node)
        logger.debug(f"Method query found {len(matches)} matches in class {class_name}")
        
        for match in matches:
            pattern_index, captures = match
            method_node = None
            method_name = None
            
            # Get method definition node
            if "method_def" in captures:
                method_node = captures["method_def"][0]  # Take first match
                
            # Get method name
            if "method_name" in captures:
                method_name_node = captures["method_name"][0]  # Take first match
                method_name = self._get_node_text(method_name_node, source_code)
            
            if method_node and method_name:
                chunk = {
                    "symbol": f"{class_name}.{method_name}",
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": self._get_node_text(method_node, source_code),
                    "chunk_type": "method"
                }
                chunks.append(chunk)
                logger.debug(f"Found method: {class_name}.{method_name} at lines {chunk['start_line']}-{chunk['end_line']}")
        
        return chunks
    
    def _get_node_text(self, node: Node, source_code: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source_code[node.start_byte:node.end_byte]