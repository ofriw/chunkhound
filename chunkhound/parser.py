"""Code parser module for ChunkHound - tree-sitter integration for Python AST parsing."""

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
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    tspython = None
    Language = None
    Parser = None
    Node = None

try:
    import tree_sitter_markdown as tsmarkdown  # type: ignore[import-untyped]
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    tsmarkdown = None

try:
    from tree_sitter_language_pack import get_language, get_parser
    JAVA_AVAILABLE = True
except ImportError:
    JAVA_AVAILABLE = False
    get_language = None
    get_parser = None

from loguru import logger


def is_tree_sitter_node(obj: Any) -> bool:
    """Check if object is a valid TreeSitterNode with required attributes."""
    return (obj is not None and 
            hasattr(obj, 'start_byte') and 
            hasattr(obj, 'end_byte') and 
            hasattr(obj, 'id'))


class CodeParser:
    """Tree-sitter based code parser for extracting semantic units."""
    
    def __init__(self):
        """Initialize the code parser."""
        self.python_language: Optional[TreeSitterLanguage] = None
        self.python_parser: Optional[TreeSitterParser] = None
        self.markdown_language: Optional[TreeSitterLanguage] = None
        self.markdown_parser: Optional[TreeSitterParser] = None
        self.java_language: Optional[TreeSitterLanguage] = None
        self.java_parser: Optional[TreeSitterParser] = None
        self._python_initialized = False
        self._markdown_initialized = False
        self._java_initialized = False
        
    def setup(self) -> None:
        """Set up tree-sitter parsers for Python, Markdown, and Java."""
        if not TREE_SITTER_AVAILABLE:
            logger.error("Tree-sitter dependencies not available")
            return
            
        logger.info("Setting up tree-sitter parsers")
        
        # Setup Python parser
        try:
            if tspython is not None and Language is not None and Parser is not None:
                self.python_language = Language(tspython.language())
                self.python_parser = Parser(self.python_language)
                self._python_initialized = True
                logger.info("Python parser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Python parser: {e}")
            self._python_initialized = False
            
        # Setup Markdown parser
        if MARKDOWN_AVAILABLE and tsmarkdown is not None:
            try:
                if Language is not None and Parser is not None:
                    self.markdown_language = Language(tsmarkdown.language())
                    self.markdown_parser = Parser(self.markdown_language)
                    self._markdown_initialized = True
                    logger.info("Markdown parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Markdown parser: {e}")
                self._markdown_initialized = False
        else:
            logger.warning("Markdown parser not available - tree_sitter_markdown not installed")
            
        # Setup Java parser
        if JAVA_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.java_language = get_language('java')
                self.java_parser = get_parser('java')
                self._java_initialized = True
                logger.info("Java parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Java parser: {e}")
                self._java_initialized = False
        else:
            logger.warning("Java parser not available - tree_sitter_language_pack not installed")
        
    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a file and extract semantic chunks based on file type.
        
        Args:
            file_path: Path to file to parse
            
        Returns:
            List of extracted chunks with metadata
        """
        # Determine file type
        suffix = file_path.suffix.lower()
        
        if suffix == '.py':
            return self._parse_python_file(file_path)
        elif suffix in ['.md', '.markdown']:
            return self._parse_markdown_file(file_path)
        elif suffix == '.java':
            return self._parse_java_file(file_path)
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return []
            
    def _parse_java_file(self, file_path: Path) -> List[Dict[str, Any]]:
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
                logger.error("Java parser initialization failed")
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
                logger.error("Java parser is None after initialization check")
                return []

            # Extract semantic units
            chunks = []
            
            # Get package context first
            package_name = self._extract_java_package(tree.root_node, source_code)
            
            chunks.extend(self._extract_java_classes(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_interfaces(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_enums(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_methods(tree.root_node, source_code, file_path, package_name))

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse Java file {file_path}: {e}")
            return []
    
    def _extract_java_package(self, tree_node: TreeSitterNode, source_code: str) -> str:
        """Extract package name from Java file.
        
        Args:
            tree_node: Root node of the Java AST
            source_code: Source code content
            
        Returns:
            Package name as string, or empty string if no package declaration found
        """
        if self.java_language is None:
            return ""
            
        try:
            query = self.java_language.query("""
                (package_declaration) @package_def
            """)
            
            matches = query.matches(tree_node)
            
            if not matches:
                return ""
                
            # Get first match and extract package node
            pattern_index, captures = matches[0]
            if "package_def" not in captures:
                return ""
                
            package_node = captures["package_def"][0]
            package_text = self._get_node_text(package_node, source_code)
            
            # Extract just the package name from the declaration
            # Expected format: "package com.example.demo;"
            package_text = package_text.strip()
            if package_text.startswith("package ") and package_text.endswith(";"):
                return package_text[8:-1].strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to extract Java package: {e}")
            return ""
    
    def _extract_java_classes(self, tree_node: TreeSitterNode, source_code: str, 
                              file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java class definitions from AST.
        
        Args:
            tree_node: Root node of the Java AST
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            
        Returns:
            List of class chunks with metadata
        """
        chunks = []
        
        if self.java_language is None:
            return []
            
        try:
            # Query for top-level classes
            query = self.java_language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
            """)
            
            matches = query.matches(tree_node)
            class_nodes = {}
            
            # Process matches using the correct format
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
                    class_nodes[class_node.id] = {"name": class_name, "node": class_node}
            
            # Process all found classes
            for node_id, class_info in class_nodes.items():
                if "name" not in class_info:
                    # Try to find name directly if not already captured
                    name_node = class_info["node"].child_by_field_name("name")
                    if name_node:
                        class_info["name"] = self._get_node_text(name_node, source_code)
                    else:
                        continue  # Skip if no name found
                
                class_name = class_info["name"]
                class_node = class_info["node"]
                
                # Get full class text
                class_text = self._get_node_text(class_node, source_code)
                
                # Build qualified name with package
                qualified_name = class_name
                if package_name:
                    qualified_name = f"{package_name}.{class_name}"
                
                # Extract annotations if present
                annotations = self._extract_java_annotations(class_node, source_code)
                
                # Check for generic type parameters
                type_params = self._extract_java_type_parameters(class_node, source_code)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "type": "class",
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": class_text,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "start_byte": class_node.start_byte,
                    "end_byte": class_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
                # Also process inner classes
                inner_chunks = self._extract_java_inner_classes(
                    class_node, source_code, file_path, package_name, class_name
                )
                chunks.extend(inner_chunks)
                
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java classes: {e}")
            return []
    
    def _extract_java_interfaces(self, tree_node: TreeSitterNode, source_code: str, 
                               file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java interface definitions from AST.
        
        Args:
            tree_node: Root node of the Java AST
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            
        Returns:
            List of interface chunks with metadata
        """
        chunks = []
        
        if self.java_language is None:
            return []
            
        try:
            # Query for interfaces
            query = self.java_language.query("""
                (interface_declaration
                    name: (identifier) @interface_name
                ) @interface_def
            """)
            
            matches = query.matches(tree_node)
            interface_nodes = {}
            
            # Process matches using the correct format
            for match in matches:
                pattern_index, captures = match
                interface_node = None
                interface_name = None
                
                # Get interface definition node
                if "interface_def" in captures:
                    interface_node = captures["interface_def"][0]  # Take first match
                    
                # Get interface name
                if "interface_name" in captures:
                    interface_name_node = captures["interface_name"][0]  # Take first match
                    interface_name = self._get_node_text(interface_name_node, source_code)
                
                if interface_node and interface_name:
                    interface_nodes[interface_node.id] = {"name": interface_name, "node": interface_node}
            
            # Process all found interfaces
            for node_id, interface_info in interface_nodes.items():
                
                interface_name = interface_info["name"]
                interface_node = interface_info["node"]
                
                # Get full interface text
                interface_text = self._get_node_text(interface_node, source_code)
                
                # Build qualified name with package
                qualified_name = interface_name
                if package_name:
                    qualified_name = f"{package_name}.{interface_name}"
                
                # Extract annotations if present
                annotations = self._extract_java_annotations(interface_node, source_code)
                
                # Check for generic type parameters
                type_params = self._extract_java_type_parameters(interface_node, source_code)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "type": "interface",
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": interface_text,
                    "start_line": interface_node.start_point[0] + 1,
                    "end_line": interface_node.end_point[0] + 1,
                    "start_byte": interface_node.start_byte,
                    "end_byte": interface_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
                # Also extract inner interfaces (less common but possible)
                body_node = None
                for i in range(interface_node.child_count):
                    child = interface_node.child(i)
                    if child and child.type == "interface_body":
                        body_node = child
                        break
                        
                if body_node:
                    inner_interfaces_query = self.java_language.query("""
                        (interface_declaration
                            name: (identifier) @inner_interface_name
                        ) @inner_interface_def
                    """)
                    
                    inner_matches = inner_interfaces_query.matches(body_node)
                    
                    # Process inner interface matches using the correct format
                    for match in inner_matches:
                        pattern_index, captures = match
                        inner_interface_node = None
                        inner_interface_name = None
                        
                        # Get inner interface definition node
                        if "inner_interface_def" in captures:
                            inner_interface_node = captures["inner_interface_def"][0]  # Take first match
                            
                        # Get inner interface name
                        if "inner_interface_name" in captures:
                            inner_interface_name_node = captures["inner_interface_name"][0]  # Take first match
                            inner_interface_name = self._get_node_text(inner_interface_name_node, source_code)
                        
                        if not inner_interface_node or not inner_interface_name:
                            continue
                        
                        inner_node = inner_interface_node
                        
                        inner_text = self._get_node_text(inner_node, source_code)
                        inner_qualified_name = f"{qualified_name}.{inner_interface_name}"
                        
                        inner_annotations = self._extract_java_annotations(inner_node, source_code)
                        inner_type_params = self._extract_java_type_parameters(inner_node, source_code)
                        
                        if inner_type_params:
                            inner_display_name = f"{inner_qualified_name}{inner_type_params}"
                        else:
                            inner_display_name = inner_qualified_name
                        
                        inner_chunk = {
                            "type": "inner_interface",
                            "language": "java",
                            "path": str(file_path),
                            "name": inner_qualified_name,
                            "display_name": inner_display_name,
                            "content": inner_text,
                            "start_line": inner_node.start_point[0] + 1,
                            "end_line": inner_node.end_point[0] + 1,
                            "start_byte": inner_node.start_byte,
                            "end_byte": inner_node.end_byte,
                            "parent_interface": qualified_name,
                        }
                        
                        if inner_annotations:
                            inner_chunk["annotations"] = inner_annotations
                        
                        chunks.append(inner_chunk)
                
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java interfaces: {e}")
            return []
    
    def _extract_java_inner_classes(self, class_node: TreeSitterNode, source_code: str, 
                                  file_path: Path, package_name: str, 
                                  outer_class_name: str) -> List[Dict[str, Any]]:
        """Extract inner classes from a Java class.
        
        Args:
            class_node: Class node to search for inner classes
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            outer_class_name: Name of the containing class
            
        Returns:
            List of inner class chunks with metadata
        """
        chunks = []
        
        if self.java_language is None:
            return []
            
        try:
            # Find the class body node
            body_node = None
            for i in range(class_node.child_count):
                child = class_node.child(i)
                if child and child.type == "class_body":
                    body_node = child
                    break
                    
            if not body_node:
                return []
                
            # Query for inner classes within the class body
            query = self.java_language.query("""
                (class_declaration
                    name: (identifier) @inner_class_name
                ) @inner_class_def
            """)
            
            matches = query.matches(body_node)
            inner_class_nodes = {}
            
            # Process matches using the correct format
            for match in matches:
                pattern_index, captures = match
                inner_class_node = None
                inner_class_name = None
                
                # Get inner class definition node
                if "inner_class_def" in captures:
                    inner_class_node = captures["inner_class_def"][0]  # Take first match
                    
                # Get inner class name
                if "inner_class_name" in captures:
                    inner_class_name_node = captures["inner_class_name"][0]  # Take first match
                    inner_class_name = self._get_node_text(inner_class_name_node, source_code)
                
                if inner_class_node and inner_class_name:
                    inner_class_nodes[inner_class_node.id] = {"name": inner_class_name, "node": inner_class_node}
            
            # Process all found inner classes
            for node_id, class_info in inner_class_nodes.items():
                inner_class_name = class_info["name"]
                inner_class_node = class_info["node"]
                
                # Get full inner class text
                inner_class_text = self._get_node_text(inner_class_node, source_code)
                
                # Build qualified name with outer class
                qualified_name = f"{outer_class_name}.{inner_class_name}"
                if package_name:
                    qualified_name = f"{package_name}.{qualified_name}"
                
                # Extract annotations if present
                annotations = self._extract_java_annotations(inner_class_node, source_code)
                
                # Check for generic type parameters
                type_params = self._extract_java_type_parameters(inner_class_node, source_code)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "type": "inner_class",
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": inner_class_text,
                    "start_line": inner_class_node.start_point[0] + 1,
                    "end_line": inner_class_node.end_point[0] + 1,
                    "start_byte": inner_class_node.start_byte,
                    "end_byte": inner_class_node.end_byte,
                    "parent_class": outer_class_name,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
                # Recursively process nested inner classes
                nested_chunks = self._extract_java_inner_classes(
                    inner_class_node, source_code, file_path, 
                    package_name, qualified_name
                )
                chunks.extend(nested_chunks)
                
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java inner classes: {e}")
            return []
    
    def _extract_java_annotations(self, node: TreeSitterNode, source_code: str) -> List[str]:
        """Extract Java annotations from a node.

        Args:
            node: Node to check for annotations
            source_code: Source code content

        Returns:
            List of annotation strings
        """
        annotations = []

        if self.java_language is None:
            return annotations

        try:
            # For Java, annotations are typically found in the modifiers child
            # Look for modifiers node which contains annotations
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "modifiers":
                    # Look for annotation children within modifiers
                    for j in range(child.child_count):
                        mod_child = child.child(j)
                        if mod_child and mod_child.type in ["annotation", "marker_annotation"]:
                            annotation_text = self._get_node_text(mod_child, source_code)
                            annotations.append(annotation_text.strip())

            # Also check direct children for annotations (fallback)
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type in ["annotation", "marker_annotation"]:
                    annotation_text = self._get_node_text(child, source_code)
                    annotations.append(annotation_text.strip())

            # Check siblings before this node for annotations (another fallback)
            parent = node.parent
            if parent:
                for i in range(parent.child_count):
                    child = parent.child(i)
                    if child and child.id == node.id:
                        break
                    if child and child.type in ["annotation", "marker_annotation"]:
                        annotation_text = self._get_node_text(child, source_code)
                        annotations.append(annotation_text.strip())

            return annotations

        except Exception as e:
            logger.error(f"Failed to extract Java annotations: {e}")
            return []
    
    def _extract_java_type_parameters(self, node: TreeSitterNode, source_code: str) -> str:
        """Extract generic type parameters from a Java node.
        
        Args:
            node: Node to check for type parameters
            source_code: Source code content
            
        Returns:
            Type parameters as a string, or empty string if none
        """
        if self.java_language is None:
            return ""
            
        try:
            # Look for type_parameters node as a child
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "type_parameters":
                    return self._get_node_text(child, source_code).strip()
            return ""
            
        except Exception as e:
            logger.error(f"Failed to extract Java type parameters: {e}")
            return ""
            
    def _extract_java_enums(self, tree_node: TreeSitterNode, source_code: str, 
                          file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java enum definitions from AST.
        
        Args:
            tree_node: Root node of the Java AST
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            
        Returns:
            List of enum chunks with metadata
        """
        chunks = []
        
        if self.java_language is None:
            return []
            
        try:
            # Query for enums
            query = self.java_language.query("""
                (enum_declaration
                    name: (identifier) @enum_name
                ) @enum_def
            """)
            
            matches = query.matches(tree_node)
            enum_nodes = {}
            
            # Process matches using the correct format
            for match in matches:
                pattern_index, captures = match
                enum_node = None
                enum_name = None
                
                # Get enum definition node
                if "enum_def" in captures:
                    enum_node = captures["enum_def"][0]  # Take first match
                    
                # Get enum name
                if "enum_name" in captures:
                    enum_name_node = captures["enum_name"][0]  # Take first match
                    enum_name = self._get_node_text(enum_name_node, source_code)
                
                if enum_node and enum_name:
                    enum_nodes[enum_node.id] = {"name": enum_name, "node": enum_node}
            
            # Process all found enums
            for node_id, enum_info in enum_nodes.items():
                
                enum_name = enum_info["name"]
                enum_node = enum_info["node"]
                
                # Get full enum text
                enum_text = self._get_node_text(enum_node, source_code)
                
                # Build qualified name with package
                qualified_name = enum_name
                if package_name:
                    qualified_name = f"{package_name}.{enum_name}"
                
                # Extract annotations if present
                annotations = self._extract_java_annotations(enum_node, source_code)
                
                # Create chunk
                chunk = {
                    "type": "enum",
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": enum_text,
                    "start_line": enum_node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "start_byte": enum_node.start_byte,
                    "end_byte": enum_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                # Extract enum constants
                constants = self._extract_java_enum_constants(enum_node, source_code)
                if constants:
                    chunk["constants"] = constants
                
                chunks.append(chunk)
                
                # Also extract enum methods
                enum_method_chunks = self._extract_java_enum_methods(
                    enum_node, source_code, file_path, package_name, qualified_name
                )
                chunks.extend(enum_method_chunks)
                
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java enums: {e}")
            return []
            
    def _extract_java_enum_constants(self, enum_node: TreeSitterNode, source_code: str) -> List[str]:
        """Extract constants from a Java enum.
        
        Args:
            enum_node: Enum node to extract constants from
            source_code: Source code content
            
        Returns:
            List of enum constant names
        """
        constants = []
        
        if self.java_language is None:
            return constants
            
        try:
            # Find the enum body node
            body_node = None
            for i in range(enum_node.child_count):
                child = enum_node.child(i)
                if child and child.type == "enum_body":
                    body_node = child
                    break
                    
            if not body_node:
                return constants
                
            # Find enum constant nodes within the body
            for i in range(body_node.child_count):
                child = body_node.child(i)
                if child and child.type == "enum_constant":
                    # Get the name of the constant
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        constant_name = self._get_node_text(name_node, source_code)
                        constants.append(constant_name)
                        
            return constants
            
        except Exception as e:
            logger.error(f"Failed to extract Java enum constants: {e}")
            return []
            
    def _extract_java_enum_methods(self, enum_node: TreeSitterNode, source_code: str,
                                file_path: Path, package_name: str, 
                                enum_name: str) -> List[Dict[str, Any]]:
        """Extract methods from a Java enum.
        
        Args:
            enum_node: Enum node to extract methods from
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            enum_name: Qualified name of the enum
            
        Returns:
            List of method chunks with metadata
        """
        method_chunks = []
        
        if self.java_language is None:
            return method_chunks
            
        try:
            # Find the enum body node
            body_node = None
            for i in range(enum_node.child_count):
                child = enum_node.child(i)
                if child and child.type == "enum_body":
                    body_node = child
                    break
                    
            if not body_node:
                return method_chunks
                
            # Query for methods within the enum body
            query = self.java_language.query("""
                (method_declaration
                    name: (identifier) @method_name
                ) @method_def
            """)
            
            matches = query.matches(body_node)
            method_nodes = {}
            
            # Process matches using the correct format
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
                    method_nodes[method_node.id] = {"name": method_name, "node": method_node}
            
            # Process all found methods
            for node_id, method_info in method_nodes.items():
                if "name" not in method_info:
                    name_node = method_info["node"].child_by_field_name("name")
                    if name_node:
                        method_info["name"] = self._get_node_text(name_node, source_code)
                    else:
                        continue
                
                method_name = method_info["name"]
                method_node = method_info["node"]
                
                # Get method parameters
                parameters = self._extract_java_method_parameters(method_node, source_code)
                param_types_str = ", ".join(parameters)
                
                # Get method return type
                return_type = self._extract_java_method_return_type(method_node, source_code)
                
                # Get full method text
                method_text = self._get_node_text(method_node, source_code)
                
                # Build qualified name
                qualified_name = f"{enum_name}.{method_name}"
                display_name = f"{qualified_name}({param_types_str})"
                
                # Extract annotations
                annotations = self._extract_java_annotations(method_node, source_code)
                
                # Check for generic type parameters
                type_params = self._extract_java_type_parameters(method_node, source_code)
                if type_params:
                    display_name = f"{qualified_name}<{type_params}>({param_types_str})"
                
                # Create chunk
                chunk = {
                    "type": "method",
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parent": enum_name,
                    "parameters": parameters,
                }
                
                if return_type:
                    chunk["return_type"] = return_type
                    
                if annotations:
                    chunk["annotations"] = annotations
                
                method_chunks.append(chunk)
                
            return method_chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java enum methods: {e}")
            return []
            
    def _extract_java_methods(self, tree_node: TreeSitterNode, source_code: str,
                            file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java method definitions from AST.
        
        Args:
            tree_node: Root node of the Java AST
            source_code: Source code content
            file_path: Path to the Java file
            package_name: Package name for context
            
        Returns:
            List of method chunks with metadata
        """
        method_chunks = []
        
        if self.java_language is None:
            return method_chunks
            
        try:
            # Find all classes first to associate methods with their classes
            class_query = self.java_language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
            """)
            
            class_matches = class_query.matches(tree_node)
            class_nodes = {}
            
            # Process class matches using the correct format
            for match in class_matches:
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
                    # Use qualified name with package
                    qualified_class_name = class_name
                    if package_name:
                        qualified_class_name = f"{package_name}.{class_name}"
                    class_nodes[class_node.id] = {
                        "name": qualified_class_name,
                        "node": class_node
                    }
            
            # Extract methods from each class
            for class_id, class_info in class_nodes.items():
                class_node = class_info["node"]
                class_name = class_info["name"]
                
                # Find the class body node
                body_node = None
                for i in range(class_node.child_count):
                    child = class_node.child(i)
                    if child and child.type == "class_body":
                        body_node = child
                        break
                        
                if not body_node:
                    continue
                    
                # Query for methods within the class body
                method_query = self.java_language.query("""
                    (method_declaration
                        name: (identifier) @method_name
                    ) @method_def
                    
                    (constructor_declaration
                        name: (identifier) @constructor_name
                    ) @constructor_def
                """)
                
                method_matches = method_query.matches(body_node)
                
                # Process method matches using the correct format
                for match in method_matches:
                    pattern_index, captures = match
                    method_node = None
                    method_name = None
                    is_constructor = False
                    
                    # Get method definition node
                    if "method_def" in captures:
                        method_node = captures["method_def"][0]  # Take first match
                        
                    # Get constructor definition node
                    elif "constructor_def" in captures:
                        method_node = captures["constructor_def"][0]  # Take first match
                        is_constructor = True
                    
                    # Get method name
                    if "method_name" in captures:
                        method_name_node = captures["method_name"][0]  # Take first match
                        method_name = self._get_node_text(method_name_node, source_code)
                    elif "constructor_name" in captures:
                        constructor_name_node = captures["constructor_name"][0]  # Take first match
                        method_name = self._get_node_text(constructor_name_node, source_code)
                        is_constructor = True
                    
                    if not method_node or not method_name:
                        continue
                    

                    
                    # Get method parameters
                    parameters = self._extract_java_method_parameters(method_node, source_code)
                    param_types_str = ", ".join(parameters)
                    
                    # Get method return type (not applicable for constructors)
                    return_type = None
                    if not is_constructor:
                        return_type = self._extract_java_method_return_type(method_node, source_code)
                    
                    # Get full method text
                    method_text = self._get_node_text(method_node, source_code)
                    
                    # Build qualified name
                    qualified_name = f"{class_name}.{method_name}"
                    display_name = f"{qualified_name}({param_types_str})"
                    
                    # Extract annotations
                    annotations = self._extract_java_annotations(method_node, source_code)
                    
                    # Check for generic type parameters
                    type_params = self._extract_java_type_parameters(method_node, source_code)
                    if type_params:
                        display_name = f"{qualified_name}<{type_params}>({param_types_str})"
                    
                    # Create chunk
                    chunk_type = "constructor" if is_constructor else "method"
                    chunk = {
                        "type": chunk_type,
                        "language": "java",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": method_text,
                        "start_line": method_node.start_point[0] + 1,
                        "end_line": method_node.end_point[0] + 1,
                        "start_byte": method_node.start_byte,
                        "end_byte": method_node.end_byte,
                        "parent": class_name,
                        "parameters": parameters,
                    }
                    
                    if return_type and not is_constructor:
                        chunk["return_type"] = return_type
                        
                    if annotations:
                        chunk["annotations"] = annotations
                    
                    method_chunks.append(chunk)
            
            return method_chunks
            
        except Exception as e:
            logger.error(f"Failed to extract Java methods: {e}")
            return []
            
    def _extract_java_method_parameters(self, method_node: TreeSitterNode, source_code: str) -> List[str]:
        """Extract parameter types from a Java method.
        
        Args:
            method_node: Method node to extract parameters from
            source_code: Source code content
            
        Returns:
            List of parameter type strings
        """
        parameters = []
        
        try:
            # Find the parameters node
            params_node = None
            for i in range(method_node.child_count):
                child = method_node.child(i)
                if child and child.type == "formal_parameters":
                    params_node = child
                    break
                    
            if not params_node:
                return parameters
                
            # Extract each parameter
            for i in range(params_node.child_count):
                child = params_node.child(i)
                if child and child.type == "formal_parameter":
                    # Get parameter type
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        param_type = self._get_node_text(type_node, source_code).strip()
                        parameters.append(param_type)
                        
            return parameters
            
        except Exception as e:
            logger.error(f"Failed to extract Java method parameters: {e}")
            return []
            
    def _extract_java_method_return_type(self, method_node: TreeSitterNode, source_code: str) -> Optional[str]:
        """Extract return type from a Java method.
        
        Args:
            method_node: Method node to extract return type from
            source_code: Source code content
            
        Returns:
            Return type as string, or None if not found
        """
        try:
            # Find the return type node
            type_node = method_node.child_by_field_name("type")
            if type_node:
                return self._get_node_text(type_node, source_code).strip()
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract Java method return type: {e}")
            return None
    
    def _parse_python_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a Python file and extract semantic chunks."""
        if not self._python_initialized:
            logger.warning("Python parser not initialized, attempting setup")
            self.setup()
            if not self._python_initialized:
                return []
        
        logger.debug(f"Parsing Python file: {file_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Parse with tree-sitter
            if self.python_parser is not None:
                tree = self.python_parser.parse(bytes(source_code, 'utf8'))
            else:
                return []
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_functions(tree.root_node, source_code))
            chunks.extend(self._extract_classes(tree.root_node, source_code))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse Python file {file_path}: {e}")
            return []
    
    def _parse_markdown_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a Markdown file and extract semantic chunks."""
        if not self._markdown_initialized:
            logger.warning("Markdown parser not initialized, attempting setup")
            self.setup()
            if not self._markdown_initialized:
                return []
        
        logger.debug(f"Parsing Markdown file: {file_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Parse with tree-sitter
            if self.markdown_parser is not None:
                tree = self.markdown_parser.parse(bytes(source_code, 'utf8'))
            else:
                return []
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_headers(tree.root_node, source_code))
            chunks.extend(self._extract_code_blocks(tree.root_node, source_code))
            chunks.extend(self._extract_paragraphs(tree.root_node, source_code))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse Markdown file {file_path}: {e}")
            return []
        
    def _extract_functions(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract function definitions from AST."""
        chunks = []
        
        # Query for function definitions
        if self.python_language is not None:
            query = self.python_language.query("""
                (function_definition
                    name: (identifier) @func_name
                ) @func_def
            """)
        else:
            return chunks
        
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
        
    def _extract_classes(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract class definitions and methods from AST."""
        chunks = []
        
        # Query for class definitions
        if self.python_language is not None:
            class_query = self.python_language.query("""
                (class_definition
                    name: (identifier) @class_name
                ) @class_def
            """)
        else:
            return chunks
        
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
    
    def _extract_methods(self, class_node: TreeSitterNode, source_code: str, class_name: str) -> List[Dict[str, Any]]:
        """Extract method definitions from a class."""
        chunks = []
        
        # Query for function definitions within the class
        if self.python_language is not None:
            method_query = self.python_language.query("""
                (function_definition
                    name: (identifier) @method_name
                ) @method_def
            """)
        else:
            return chunks
        
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
    
    def _get_node_text(self, node: TreeSitterNode, source_code: str) -> str:
        """Extract text content from a tree-sitter node safely."""
        if not is_tree_sitter_node(node):
            raise TypeError(f"Expected TreeSitterNode, got {type(node).__name__}")
        return source_code[node.start_byte:node.end_byte]
    
    def _extract_headers(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract markdown headers from AST."""
        chunks = []
        
        # Query for headers (ATX headers with #)
        if self.markdown_language is not None:
            query = self.markdown_language.query("""
            (atx_heading
                (atx_h1_marker) @h1_marker
                heading_content: (_)* @h1_content
            ) @h1_heading
            (atx_heading
                (atx_h2_marker) @h2_marker
                heading_content: (_)* @h2_content
            ) @h2_heading
            (atx_heading
                (atx_h3_marker) @h3_marker
                heading_content: (_)* @h3_content
            ) @h3_heading
            (atx_heading
                (atx_h4_marker) @h4_marker
                heading_content: (_)* @h4_content
            ) @h4_heading
            (atx_heading
                (atx_h5_marker) @h5_marker
                heading_content: (_)* @h5_content
            ) @h5_heading
            (atx_heading
                (atx_h6_marker) @h6_marker
                heading_content: (_)* @h6_content
            ) @h6_heading
        """)
        else:
            return chunks
        
        try:
            matches = query.matches(tree_node)
            logger.debug(f"Header query found {len(matches)} matches")
            
            for match in matches:
                pattern_index, captures = match
                
                # Determine header level and extract content
                for level in range(1, 7):
                    heading_key = f"h{level}_heading"
                    content_key = f"h{level}_content"
                    
                    if heading_key in captures and content_key in captures:
                        heading_node = captures[heading_key][0]
                        content_nodes = captures[content_key]
                        
                        # Get header text
                        if content_nodes:
                            header_text = " ".join(
                                self._get_node_text(node, source_code).strip() 
                                for node in content_nodes
                            )
                        else:
                            header_text = self._get_node_text(heading_node, source_code).strip()
                        
                        chunk = {
                            "symbol": header_text,
                            "start_line": heading_node.start_point[0] + 1,
                            "end_line": heading_node.end_point[0] + 1,
                            "code": self._get_node_text(heading_node, source_code),
                            "chunk_type": f"header_{level}",
                            "language_info": "markdown"
                        }
                        chunks.append(chunk)
                        logger.debug(f"Found header level {level}: {header_text}")
                        break
        
        except Exception as e:
            logger.error(f"Failed to extract headers: {e}")
        
        return chunks
    
    def _extract_code_blocks(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract markdown code blocks from AST."""
        chunks = []
        
        # Query for fenced code blocks
        if self.markdown_language is not None:
            query = self.markdown_language.query("""
                (fenced_code_block
                    (info_string) @lang
                    (code_fence_content) @code_content
                ) @code_block
            """)
        else:
            return chunks
        
        try:
            matches = query.matches(tree_node)
            logger.debug(f"Code block query found {len(matches)} matches")
            
            for match in matches:
                pattern_index, captures = match
                
                if "code_block" in captures:
                    code_block_node = captures["code_block"][0]
                    
                    # Get language info if available
                    language_info = "text"
                    if "lang" in captures:
                        lang_node = captures["lang"][0]
                        language_info = self._get_node_text(lang_node, source_code).strip()
                    
                    chunk = {
                        "symbol": f"code_block_{language_info}",
                        "start_line": code_block_node.start_point[0] + 1,
                        "end_line": code_block_node.end_point[0] + 1,
                        "code": self._get_node_text(code_block_node, source_code),
                        "chunk_type": "code_block",
                        "language_info": language_info
                    }
                    chunks.append(chunk)
                    logger.debug(f"Found code block ({language_info}) at lines {chunk['start_line']}-{chunk['end_line']}")
        
        except Exception as e:
            logger.error(f"Failed to extract code blocks: {e}")
        
        return chunks
    
    def _extract_paragraphs(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract markdown paragraphs from AST."""
        chunks = []
        
        # Query for paragraph nodes
        if self.markdown_language is not None:
            query = self.markdown_language.query("""
                (paragraph) @paragraph
            """)
        else:
            return chunks
        
        try:
            matches = query.matches(tree_node)
            logger.debug(f"Paragraph query found {len(matches)} matches")
            
            for match in matches:
                pattern_index, captures = match
                
                if "paragraph" in captures:
                    para_node = captures["paragraph"][0]
                    para_text = self._get_node_text(para_node, source_code).strip()
                    
                    # Skip very short paragraphs
                    if len(para_text) < 20:
                        continue
                    
                    # Create a brief symbol from first few words
                    words = para_text.split()[:5]
                    symbol = " ".join(words) + ("..." if len(words) == 5 else "")
                    
                    chunk = {
                        "symbol": symbol,
                        "start_line": para_node.start_point[0] + 1,
                        "end_line": para_node.end_point[0] + 1,
                        "code": para_text,
                        "chunk_type": "paragraph",
                        "language_info": "markdown"
                    }
                    chunks.append(chunk)
                    logger.debug(f"Found paragraph at lines {chunk['start_line']}-{chunk['end_line']}")
        
        except Exception as e:
            logger.error(f"Failed to extract paragraphs: {e}")
        
        return chunks