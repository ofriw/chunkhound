#!/usr/bin/env python3
"""
Java Parser Implementation - Sample code for ChunkHound Java language support
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language, Parser, Node
    TreeSitterLanguage = Language
    TreeSitterParser = Parser
    TreeSitterNode = Node
else:
    TreeSitterLanguage = Any
    TreeSitterParser = Any
    TreeSitterNode = Any

try:
    from tree_sitter_language_pack import get_language, get_parser
    JAVA_AVAILABLE = True
except ImportError:
    JAVA_AVAILABLE = False
    get_language = None
    get_parser = None

from loguru import logger


class JavaParser:
    """Tree-sitter based Java parser for extracting semantic units."""
    
    def __init__(self):
        """Initialize the Java parser."""
        self.java_language: Optional[TreeSitterLanguage] = None
        self.java_parser: Optional[TreeSitterParser] = None
        self._java_initialized = False
        
    def setup(self) -> None:
        """Set up tree-sitter parser for Java."""
        if not JAVA_AVAILABLE:
            logger.error("Tree-sitter-language-pack not available")
            return

        logger.info("Setting up Java tree-sitter parser")

        # Setup Java parser
        try:
            if get_language is not None and get_parser is not None:
                self.java_language = get_language('java')
                self.java_parser = get_parser('java')
                self._java_initialized = True
                logger.info("Java parser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Java parser: {e}")
            self._java_initialized = False

    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a Java file and extract semantic chunks.
        
        Args:
            file_path: Path to Java file to parse
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._java_initialized:
            logger.warning("Java parser not initialized, attempting setup")
            self.setup()
            if not self._java_initialized:
                return []

        logger.debug(f"Parsing Java file: {file_path}")

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse with tree-sitter
            if self.java_parser is not None:
                tree = self.java_parser.parse(bytes(source_code, 'utf8'))
            else:
                return []

            # Extract package name for context
            package_name = self._extract_package_name(tree.root_node, source_code) or ""

            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_classes(tree.root_node, source_code, package_name))
            chunks.extend(self._extract_interfaces(tree.root_node, source_code, package_name))
            chunks.extend(self._extract_enums(tree.root_node, source_code, package_name))

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse Java file {file_path}: {e}")
            return []

    def _extract_package_name(self, tree_node: TreeSitterNode, source_code: str) -> Optional[str]:
        """Extract package name from AST."""
        if self.java_language is None:
            return None
        
        query = self.java_language.query("""
            (package_declaration) @package_def
        """)
        
        matches = query.matches(tree_node)
        if not matches:
            return None
            
        package_node = matches[0][1].get("package_def", [None])[0]
        if package_node is None:
            return None
            
        package_text = self._get_node_text(package_node, source_code)
        # Extract just the package name without "package" keyword and semicolon
        if package_text.startswith("package "):
            package_text = package_text[8:]
        if package_text.endswith(";"):
            package_text = package_text[:-1]
        return package_text.strip()
    
    def _extract_classes(self, tree_node: TreeSitterNode, source_code: str, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java class definitions from AST."""
        chunks = []
        
        if self.java_language is None:
            return chunks
            
        query = self.java_language.query("""
            (class_declaration
                name: (identifier) @class_name
            ) @class_def
        """)
        
        matches = query.matches(tree_node)
        logger.debug(f"Class query found {len(matches)} matches")
        
        for match in matches:
            captures = match[1]
            
            class_node = captures.get("class_def", [None])[0]
            class_name_node = captures.get("class_name", [None])[0]
            
            if class_node is None or class_name_node is None:
                continue
                
            class_name = self._get_node_text(class_name_node, source_code)
            
            # Determine if this is a top-level class or inner class
            is_inner_class = self._is_inner_class(class_node)
            
            # For inner classes, we need to determine the parent class
            parent_class = ""
            if is_inner_class:
                parent_class = self._get_parent_class_name(class_node, source_code)
                symbol = f"{package_name}.{parent_class}.{class_name}" if package_name else f"{parent_class}.{class_name}"
            else:
                symbol = f"{package_name}.{class_name}" if package_name else class_name
            
            # Get class generics if present
            generics = self._extract_type_parameters(class_node, source_code)
            if generics:
                symbol = f"{symbol}<{generics}>"
                
            chunk = {
                "symbol": symbol,
                "start_line": class_node.start_point[0] + 1,  # Convert to 1-indexed
                "end_line": class_node.end_point[0] + 1,
                "code": self._get_node_text(class_node, source_code),
                "chunk_type": "class",
                "language_info": "java"
            }
            chunks.append(chunk)
            logger.debug(f"Found class: {symbol} at lines {chunk['start_line']}-{chunk['end_line']}")
            
            # Extract methods within this class
            method_chunks = self._extract_methods(class_node, source_code, symbol)
            chunks.extend(method_chunks)
            
        return chunks
    
    def _extract_interfaces(self, tree_node: TreeSitterNode, source_code: str, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java interface definitions from AST."""
        chunks = []
        
        if self.java_language is None:
            return chunks
            
        query = self.java_language.query("""
            (interface_declaration
                name: (identifier) @interface_name
            ) @interface_def
        """)
        
        matches = query.matches(tree_node)
        logger.debug(f"Interface query found {len(matches)} matches")
        
        for match in matches:
            captures = match[1]
            
            interface_node = captures.get("interface_def", [None])[0]
            interface_name_node = captures.get("interface_name", [None])[0]
            
            if interface_node is None or interface_name_node is None:
                continue
                
            interface_name = self._get_node_text(interface_name_node, source_code)
            
            # Determine if this is a top-level interface or inner interface
            is_inner = self._is_inner_class(interface_node)
            
            # For inner interfaces, we need to determine the parent class
            parent_class = ""
            if is_inner:
                parent_class = self._get_parent_class_name(interface_node, source_code)
                symbol = f"{package_name}.{parent_class}.{interface_name}" if package_name else f"{parent_class}.{interface_name}"
            else:
                symbol = f"{package_name}.{interface_name}" if package_name else interface_name
            
            # Get interface generics if present
            generics = self._extract_type_parameters(interface_node, source_code)
            if generics:
                symbol = f"{symbol}<{generics}>"
                
            chunk = {
                "symbol": symbol,
                "start_line": interface_node.start_point[0] + 1,
                "end_line": interface_node.end_point[0] + 1,
                "code": self._get_node_text(interface_node, source_code),
                "chunk_type": "interface",
                "language_info": "java"
            }
            chunks.append(chunk)
            logger.debug(f"Found interface: {symbol} at lines {chunk['start_line']}-{chunk['end_line']}")
            
            # Extract methods within this interface
            method_chunks = self._extract_methods(interface_node, source_code, symbol)
            chunks.extend(method_chunks)
            
        return chunks
    
    def _extract_enums(self, tree_node: TreeSitterNode, source_code: str, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java enum definitions from AST."""
        chunks = []
        
        if self.java_language is None:
            return chunks
            
        query = self.java_language.query("""
            (enum_declaration
                name: (identifier) @enum_name
            ) @enum_def
        """)
        
        matches = query.matches(tree_node)
        logger.debug(f"Enum query found {len(matches)} matches")
        
        for match in matches:
            captures = match[1]
            
            enum_node = captures.get("enum_def", [None])[0]
            enum_name_node = captures.get("enum_name", [None])[0]
            
            if enum_node is None or enum_name_node is None:
                continue
                
            enum_name = self._get_node_text(enum_name_node, source_code)
            
            # Determine if this is a top-level enum or inner enum
            is_inner = self._is_inner_class(enum_node)
            
            # For inner enums, we need to determine the parent class
            parent_class = ""
            if is_inner:
                parent_class = self._get_parent_class_name(enum_node, source_code)
                symbol = f"{package_name}.{parent_class}.{enum_name}" if package_name else f"{parent_class}.{enum_name}"
            else:
                symbol = f"{package_name}.{enum_name}" if package_name else enum_name
                
            chunk = {
                "symbol": symbol,
                "start_line": enum_node.start_point[0] + 1,
                "end_line": enum_node.end_point[0] + 1,
                "code": self._get_node_text(enum_node, source_code),
                "chunk_type": "enum",
                "language_info": "java"
            }
            chunks.append(chunk)
            logger.debug(f"Found enum: {symbol} at lines {chunk['start_line']}-{chunk['end_line']}")
            
            # Extract methods within this enum
            method_chunks = self._extract_methods(enum_node, source_code, symbol)
            chunks.extend(method_chunks)
            
        return chunks
    
    def _extract_methods(self, class_node: TreeSitterNode, source_code: str, class_symbol: str) -> List[Dict[str, Any]]:
        """Extract method definitions from a class, interface, or enum."""
        chunks = []
        
        if self.java_language is None:
            return chunks
            
        query = self.java_language.query("""
            (method_declaration
                name: (identifier) @method_name
                parameters: (formal_parameters) @method_params
            ) @method_def
        """)
        
        matches = query.matches(class_node)
        logger.debug(f"Method query found {len(matches)} matches in {class_symbol}")
        
        for match in matches:
            captures = match[1]
            
            method_node = captures.get("method_def", [None])[0]
            method_name_node = captures.get("method_name", [None])[0]
            method_params_node = captures.get("method_params", [None])[0]
            
            if method_node is None or method_name_node is None:
                continue
                
            method_name = self._get_node_text(method_name_node, source_code)
            
            # Extract parameter types for method signature
            param_types = ""
            if method_params_node is not None:
                param_types = self._extract_parameter_types(method_params_node, source_code)
                
            # Get method generics if present
            generics = self._extract_type_parameters(method_node, source_code)
            if generics:
                method_signature = f"{method_name}<{generics}>({param_types})"
            else:
                method_signature = f"{method_name}({param_types})"
                
            symbol = f"{class_symbol}.{method_signature}"
                
            chunk = {
                "symbol": symbol,
                "start_line": method_node.start_point[0] + 1,
                "end_line": method_node.end_point[0] + 1,
                "code": self._get_node_text(method_node, source_code),
                "chunk_type": "method",
                "language_info": "java"
            }
            chunks.append(chunk)
            logger.debug(f"Found method: {symbol} at lines {chunk['start_line']}-{chunk['end_line']}")
            
        return chunks
    
    def _extract_parameter_types(self, params_node: TreeSitterNode, source_code: str) -> str:
        """Extract parameter types from a formal_parameters node."""
        if self.java_language is None:
            return ""
            
        query = self.java_language.query("""
            (formal_parameter
                type: (_) @param_type
            ) @param
        """)
        
        matches = query.matches(params_node)
        param_types = []
        
        for match in matches:
            captures = match[1]
            
            param_type_node = captures.get("param_type", [None])[0]
            if param_type_node is not None:
                param_type = self._get_node_text(param_type_node, source_code)
                param_types.append(param_type)
                
        return ", ".join(param_types)
    
    def _extract_type_parameters(self, node: TreeSitterNode, source_code: str) -> str:
        """Extract type parameters (generics) from a node."""
        if self.java_language is None:
            return ""
            
        query = self.java_language.query("""
            (type_parameters) @type_params
        """)
        
        matches = query.matches(node)
        if not matches:
            return ""
            
        type_params_node = matches[0][1].get("type_params", [None])[0]
        if type_params_node is None:
            return ""
            
        # Extract just the content between < and >
        params_text = self._get_node_text(type_params_node, source_code)
        if params_text.startswith("<") and params_text.endswith(">"):
            return params_text[1:-1]
        return params_text
    
    def _is_inner_class(self, node: TreeSitterNode) -> bool:
        """Determine if a class is an inner class based on its parent nodes."""
        parent = node.parent
        if parent is None:
            return False
            
        # Check if parent is a class_body, which would mean this is an inner class
        return parent.type == "class_body"
    
    def _get_parent_class_name(self, node: TreeSitterNode, source_code: str) -> str:
        """Get the name of the parent class for an inner class."""
        # Navigate up to the class_body
        parent = node.parent
        if parent is None or parent.type != "class_body":
            return ""
            
        # Then up to the class_declaration
        class_node = parent.parent
        if class_node is None or class_node.type != "class_declaration":
            return ""
            
        # Find the class name
        for child in class_node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source_code)
                
        return ""
    
    def _get_node_text(self, node: TreeSitterNode, source_code: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source_code[node.start_byte:node.end_byte]


# Example usage
if __name__ == "__main__":
    parser = JavaParser()
    parser.setup()
    
    # Create a temporary Java file
    import tempfile
    
    SAMPLE_JAVA_CODE = """
    package com.example.demo;
    
    import java.util.ArrayList;
    import java.util.List;
    
    /**
     * Example Java class
     */
    public class Sample<T> {
        private List<T> items = new ArrayList<>();
        
        public void addItem(T item) {
            items.add(item);
        }
        
        public List<T> getItems() {
            return new ArrayList<>(items);
        }
        
        public class Inner {
            public void process() {
                System.out.println("Processing...");
            }
        }
        
        public interface Processor<U> {
            void process(U item);
        }
    }
    """
    
    with tempfile.NamedTemporaryFile(suffix=".java", mode="w") as f:
        f.write(SAMPLE_JAVA_CODE)
        f.flush()
        
        chunks = parser.parse_file(Path(f.name))
        
        print(f"\nExtracted {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks):
            print(f"{i+1}. {chunk['chunk_type']}: {chunk['symbol']} (lines {chunk['start_line']}-{chunk['end_line']})")