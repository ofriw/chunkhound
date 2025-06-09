"""Java language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    from tree_sitter_language_pack import get_language, get_parser
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    JAVA_AVAILABLE = True
except ImportError:
    JAVA_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class JavaParser:
    """Java language parser using tree-sitter."""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize Java parser.
        
        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False
        
        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.JAVA,
            chunk_types={
                ChunkType.CLASS,
                ChunkType.INTERFACE, 
                ChunkType.METHOD,
                ChunkType.CONSTRUCTOR,
                ChunkType.ENUM,
                ChunkType.FIELD
            },
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=True,
            include_comments=False,
            include_docstrings=True,
            max_depth=10,
            use_cache=True
        )
        
        # Initialize if available
        if JAVA_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize the Java parser.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not JAVA_AVAILABLE:
            logger.error("Java tree-sitter support not available")
            return False
        
        try:
            if get_language and get_parser:
                self._language = get_language('java')
                self._parser = get_parser('java')
                self._initialized = True
                logger.debug("Java parser initialized successfully")
                return True
            else:
                logger.error("Java parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Java parser: {e}")
            return False
    
    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.JAVA
    
    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types
    
    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return JAVA_AVAILABLE and self._initialized
    
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a Java file and extract semantic chunks.
        
        Args:
            file_path: Path to Java file
            source: Optional source code string
            
        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []
        
        if not self.is_available:
            errors.append("Java parser not available")
            return ParseResult(
                chunks=chunks,
                language=self.language,
                total_chunks=0,
                parse_time=time.time() - start_time,
                errors=errors,
                warnings=warnings,
                metadata={"file_path": str(file_path)}
            )
        
        try:
            # Read source if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
            
            # Parse with tree-sitter
            if self._parser is None:
                errors.append("Java parser not initialized")
                return ParseResult(
                    chunks=chunks,
                    language=self.language,
                    total_chunks=0,
                    parse_time=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                    metadata={"file_path": str(file_path)}
                )
            
            tree = self._parser.parse(bytes(source, 'utf8'))
            
            # Extract package name for context
            package_name = self._extract_package(tree.root_node, source) if tree else ""
            
            # Extract semantic units
            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(self._extract_classes(tree.root_node, source, file_path, package_name))
            
            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(self._extract_interfaces(tree.root_node, source, file_path, package_name))
            
            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(self._extract_enums(tree.root_node, source, file_path, package_name))
            
            if ChunkType.METHOD in self._config.chunk_types or ChunkType.CONSTRUCTOR in self._config.chunk_types:
                chunks.extend(self._extract_methods(tree.root_node, source, file_path, package_name))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to parse Java file {file_path}: {e}"
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
                "package_name": package_name if 'package_name' in locals() else ""
            }
        )
    
    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte:node.end_byte]
    
    def _extract_package(self, tree_node: TSNode, source: str) -> str:
        """Extract package name from Java file.
        
        Args:
            tree_node: Root node of the Java AST
            source: Source code content
            
        Returns:
            Package name as string, or empty string if no package declaration found
        """
        try:
            if self._language is None:
                return ""
                
            query = self._language.query("""
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
            package_text = self._get_node_text(package_node, source)
            
            # Extract just the package name from the declaration
            # Expected format: "package com.example.demo;"
            package_text = package_text.strip()
            if package_text.startswith("package ") and package_text.endswith(";"):
                return package_text[8:-1].strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to extract Java package: {e}")
            return ""
    
    def _extract_classes(self, tree_node: TSNode, source: str, 
                        file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java class definitions from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            # Query for top-level classes
            query = self._language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "class_def" not in captures or "class_name" not in captures:
                    continue
                
                class_node = captures["class_def"][0]
                class_name_node = captures["class_name"][0]
                class_name = self._get_node_text(class_name_node, source)
                
                # Get full class text
                class_text = self._get_node_text(class_node, source)
                
                # Build qualified name with package
                qualified_name = class_name
                if package_name:
                    qualified_name = f"{package_name}.{class_name}"
                
                # Extract annotations if present
                annotations = self._extract_annotations(class_node, source)
                
                # Check for generic type parameters
                type_params = self._extract_type_parameters(class_node, source)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": class_text,
                    "start_byte": class_node.start_byte,
                    "end_byte": class_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
                # Also process inner classes
                inner_chunks = self._extract_inner_classes(
                    class_node, source, file_path, package_name, class_name
                )
                chunks.extend(inner_chunks)
                
        except Exception as e:
            logger.error(f"Failed to extract Java classes: {e}")
        
        return chunks
    
    def _extract_interfaces(self, tree_node: TSNode, source: str, 
                           file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java interface definitions from AST."""
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
                
                # Extract annotations if present
                annotations = self._extract_annotations(interface_node, source)
                
                # Check for generic type parameters
                type_params = self._extract_type_parameters(interface_node, source)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": interface_node.start_point[0] + 1,
                    "end_line": interface_node.end_point[0] + 1,
                    "code": interface_text,
                    "chunk_type": ChunkType.INTERFACE.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": interface_text,
                    "start_byte": interface_node.start_byte,
                    "end_byte": interface_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Java interfaces: {e}")
        
        return chunks
    
    def _extract_enums(self, tree_node: TSNode, source: str, 
                      file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java enum definitions from AST."""
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
            
            for match in matches:
                pattern_index, captures = match
                
                if "enum_def" not in captures or "enum_name" not in captures:
                    continue
                
                enum_node = captures["enum_def"][0]
                enum_name_node = captures["enum_name"][0]
                enum_name = self._get_node_text(enum_name_node, source)
                
                # Get full enum text
                enum_text = self._get_node_text(enum_node, source)
                
                # Build qualified name with package
                qualified_name = enum_name
                if package_name:
                    qualified_name = f"{package_name}.{enum_name}"
                
                # Extract annotations if present
                annotations = self._extract_annotations(enum_node, source)
                
                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": enum_node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "code": enum_text,
                    "chunk_type": ChunkType.ENUM.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": enum_text,
                    "start_byte": enum_node.start_byte,
                    "end_byte": enum_node.end_byte,
                }
                
                # Add annotations if found
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Java enums: {e}")
        
        return chunks
    
    def _extract_methods(self, tree_node: TSNode, source: str,
                        file_path: Path, package_name: str) -> List[Dict[str, Any]]:
        """Extract Java method definitions from AST."""
        method_chunks = []
        
        try:
            if self._language is None:
                return method_chunks
                
            # Find all classes first to associate methods with their classes
            class_query = self._language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
            """)
            
            class_matches = class_query.matches(tree_node)
            
            for match in class_matches:
                pattern_index, captures = match
                
                if "class_def" not in captures or "class_name" not in captures:
                    continue
                
                class_node = captures["class_def"][0]
                class_name_node = captures["class_name"][0]
                class_name = self._get_node_text(class_name_node, source)
                
                # Use qualified name with package
                qualified_class_name = class_name
                if package_name:
                    qualified_class_name = f"{package_name}.{class_name}"
                
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
                if self._language is None:
                    continue
                    
                method_query = self._language.query("""
                    (method_declaration
                        name: (identifier) @method_name
                    ) @method_def
                    
                    (constructor_declaration
                        name: (identifier) @constructor_name
                    ) @constructor_def
                """)
                
                method_matches = method_query.matches(body_node)
                
                for method_match in method_matches:
                    pattern_index, captures = method_match
                    method_node = None
                    method_name = None
                    is_constructor = False
                    
                    # Get method definition node
                    if "method_def" in captures:
                        method_node = captures["method_def"][0]
                        
                    # Get constructor definition node
                    elif "constructor_def" in captures:
                        method_node = captures["constructor_def"][0]
                        is_constructor = True
                    
                    # Get method name
                    if "method_name" in captures:
                        method_name_node = captures["method_name"][0]
                        method_name = self._get_node_text(method_name_node, source)
                    elif "constructor_name" in captures:
                        constructor_name_node = captures["constructor_name"][0]
                        method_name = self._get_node_text(constructor_name_node, source)
                        is_constructor = True
                    
                    if not method_node or not method_name:
                        continue
                    
                    # Skip if we don't want this chunk type
                    if is_constructor and ChunkType.CONSTRUCTOR not in self._config.chunk_types:
                        continue
                    if not is_constructor and ChunkType.METHOD not in self._config.chunk_types:
                        continue
                    
                    # Get method parameters
                    parameters = self._extract_method_parameters(method_node, source)
                    param_types_str = ", ".join(parameters)
                    
                    # Get method return type (not applicable for constructors)
                    return_type = None
                    if not is_constructor:
                        return_type = self._extract_method_return_type(method_node, source)
                    
                    # Get full method text
                    method_text = self._get_node_text(method_node, source)
                    
                    # Build qualified name
                    qualified_name = f"{qualified_class_name}.{method_name}"
                    display_name = f"{qualified_name}({param_types_str})"
                    
                    # Extract annotations
                    annotations = self._extract_annotations(method_node, source)
                    
                    # Check for generic type parameters
                    type_params = self._extract_type_parameters(method_node, source)
                    if type_params:
                        display_name = f"{qualified_name}<{type_params}>({param_types_str})"
                    
                    # Create chunk
                    chunk_type_enum = ChunkType.CONSTRUCTOR if is_constructor else ChunkType.METHOD
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": method_node.start_point[0] + 1,
                        "end_line": method_node.end_point[0] + 1,
                        "code": method_text,
                        "chunk_type": chunk_type_enum.value,
                        "language": "java",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": method_text,
                        "start_byte": method_node.start_byte,
                        "end_byte": method_node.end_byte,
                        "parent": qualified_class_name,
                        "parameters": parameters,
                    }
                    
                    if return_type and not is_constructor:
                        chunk["return_type"] = return_type
                        
                    if annotations:
                        chunk["annotations"] = annotations
                    
                    method_chunks.append(chunk)
            
        except Exception as e:
            logger.error(f"Failed to extract Java methods: {e}")
        
        return method_chunks
    
    def _extract_inner_classes(self, class_node: TSNode, source: str, 
                              file_path: Path, package_name: str, 
                              outer_class_name: str) -> List[Dict[str, Any]]:
        """Extract inner classes from a Java class."""
        chunks = []
        
        try:
            # Find the class body
            body_node = None
            for i in range(class_node.child_count):
                child = class_node.child(i)
                if child and child.type == "class_body":
                    body_node = child
                    break
            
            if not body_node:
                return chunks
            
            # Query for inner classes
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (class_declaration
                    name: (identifier) @inner_class_name
                ) @inner_class_def
            """)
            
            matches = query.matches(body_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "inner_class_def" not in captures or "inner_class_name" not in captures:
                    continue
                
                inner_class_node = captures["inner_class_def"][0]
                inner_class_name_node = captures["inner_class_name"][0]
                inner_class_name = self._get_node_text(inner_class_name_node, source)
                
                inner_text = self._get_node_text(inner_class_node, source)
                
                # Build qualified name
                outer_qualified_name = outer_class_name
                if package_name:
                    outer_qualified_name = f"{package_name}.{outer_class_name}"
                inner_qualified_name = f"{outer_qualified_name}.{inner_class_name}"
                
                annotations = self._extract_annotations(inner_class_node, source)
                type_params = self._extract_type_parameters(inner_class_node, source)
                
                if type_params:
                    display_name = f"{inner_qualified_name}{type_params}"
                else:
                    display_name = inner_qualified_name
                
                chunk = {
                    "symbol": inner_qualified_name,
                    "start_line": inner_class_node.start_point[0] + 1,
                    "end_line": inner_class_node.end_point[0] + 1,
                    "code": inner_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": inner_qualified_name,
                    "display_name": display_name,
                    "content": inner_text,
                    "start_byte": inner_class_node.start_byte,
                    "end_byte": inner_class_node.end_byte,
                    "parent": outer_qualified_name,
                }
                
                if annotations:
                    chunk["annotations"] = annotations
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Java inner classes: {e}")
        
        return chunks
    
    def _extract_annotations(self, node: TSNode, source: str) -> List[str]:
        """Extract Java annotations from a node."""
        annotations = []
        
        try:
            if self._language is None:
                return annotations
            # For Java, annotations are typically found in the modifiers child
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "modifiers":
                    # Look for annotation children within modifiers
                    for j in range(child.child_count):
                        mod_child = child.child(j)
                        if mod_child and mod_child.type in ["annotation", "marker_annotation"]:
                            annotation_text = self._get_node_text(mod_child, source)
                            annotations.append(annotation_text.strip())
            
            # Also check direct children for annotations (fallback)
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type in ["annotation", "marker_annotation"]:
                    annotation_text = self._get_node_text(child, source)
                    annotations.append(annotation_text.strip())
            
        except Exception as e:
            logger.error(f"Failed to extract Java annotations: {e}")
        
        return annotations
    
    def _extract_type_parameters(self, node: TSNode, source: str) -> str:
        """Extract generic type parameters from a Java node."""
        try:
            if self._language is None:
                return ""
            # Look for type_parameters node as a child
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "type_parameters":
                    return self._get_node_text(child, source).strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to extract Java type parameters: {e}")
            return ""
    
    def _extract_method_parameters(self, method_node: TSNode, source: str) -> List[str]:
        """Extract parameter types from a Java method."""
        parameters = []
        
        try:
            if self._language is None:
                return parameters
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
                        param_type = self._get_node_text(type_node, source).strip()
                        parameters.append(param_type)
                        
        except Exception as e:
            logger.error(f"Failed to extract Java method parameters: {e}")
        
        return parameters
    
    def _extract_method_return_type(self, method_node: TSNode, source: str) -> Optional[str]:
        """Extract return type from a Java method."""
        try:
            if self._language is None:
                return None
            # Find the return type node
            type_node = method_node.child_by_field_name("type")
            if type_node:
                return self._get_node_text(type_node, source).strip()
            return None
        except Exception as e:
            logger.error(f"Failed to extract Java method return type: {e}")
            return None