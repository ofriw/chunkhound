"""C# language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    from tree_sitter_language_pack import get_language, get_parser
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    CSHARP_AVAILABLE = True
except ImportError:
    CSHARP_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class CSharpParser:
    """C# language parser using tree-sitter."""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize C# parser.
        
        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False
        
        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.CSHARP,
            chunk_types={
                ChunkType.CLASS,
                ChunkType.INTERFACE, 
                ChunkType.METHOD,
                ChunkType.CONSTRUCTOR,
                ChunkType.ENUM,
                ChunkType.STRUCT,
                ChunkType.PROPERTY,
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
        if CSHARP_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize the C# parser.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not CSHARP_AVAILABLE:
            logger.error("C# tree-sitter support not available")
            return False
        
        try:
            if get_language and get_parser:
                self._language = get_language('csharp')
                self._parser = get_parser('csharp')
                self._initialized = True
                logger.debug("C# parser initialized successfully")
                return True
            else:
                logger.error("C# parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize C# parser: {e}")
            return False
    
    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.CSHARP
    
    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types
    
    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return CSHARP_AVAILABLE and self._initialized
    
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a C# file and extract semantic chunks.
        
        Args:
            file_path: Path to C# file
            source: Optional source code string
            
        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []
        
        if not self.is_available:
            errors.append("C# parser not available")
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
                errors.append("C# parser not initialized")
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
            
            # Extract namespace context
            namespace_nodes = self._extract_namespace_nodes(tree.root_node, source)
            
            if namespace_nodes:
                # Process each namespace separately
                for namespace_node, namespace_name in namespace_nodes:
                    if ChunkType.CLASS in self._config.chunk_types:
                        chunks.extend(self._extract_classes(namespace_node, source, file_path, namespace_name))
                    
                    if ChunkType.INTERFACE in self._config.chunk_types:
                        chunks.extend(self._extract_interfaces(namespace_node, source, file_path, namespace_name))
                    
                    if ChunkType.STRUCT in self._config.chunk_types:
                        chunks.extend(self._extract_structs(namespace_node, source, file_path, namespace_name))
                    
                    if ChunkType.ENUM in self._config.chunk_types:
                        chunks.extend(self._extract_enums(namespace_node, source, file_path, namespace_name))
                    
                    if ChunkType.METHOD in self._config.chunk_types or ChunkType.CONSTRUCTOR in self._config.chunk_types:
                        chunks.extend(self._extract_methods(namespace_node, source, file_path, namespace_name))
            else:
                # No namespace declarations - process entire file with empty namespace
                if ChunkType.CLASS in self._config.chunk_types:
                    chunks.extend(self._extract_classes(tree.root_node, source, file_path, ""))
                
                if ChunkType.INTERFACE in self._config.chunk_types:
                    chunks.extend(self._extract_interfaces(tree.root_node, source, file_path, ""))
                
                if ChunkType.STRUCT in self._config.chunk_types:
                    chunks.extend(self._extract_structs(tree.root_node, source, file_path, ""))
                
                if ChunkType.ENUM in self._config.chunk_types:
                    chunks.extend(self._extract_enums(tree.root_node, source, file_path, ""))
                
                if ChunkType.METHOD in self._config.chunk_types or ChunkType.CONSTRUCTOR in self._config.chunk_types:
                    chunks.extend(self._extract_methods(tree.root_node, source, file_path, ""))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to parse C# file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            namespace_nodes = []  # Set default value on error
        
        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={
                "file_path": str(file_path),
                "namespace_count": len(namespace_nodes) if namespace_nodes else 0
            }
        )
    
    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte:node.end_byte]
    
    def _extract_namespace_nodes(self, tree_node: TSNode, source: str) -> List[Tuple[TSNode, str]]:
        """Extract all namespace nodes and their names from C# file."""
        namespace_nodes = []
        
        try:
            if self._language is None:
                return namespace_nodes
                
            query = self._language.query("""
                (namespace_declaration
                    name: (qualified_name) @namespace_name
                ) @namespace_def
                
                (namespace_declaration
                    name: (identifier) @namespace_name
                ) @namespace_def
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "namespace_def" not in captures or "namespace_name" not in captures:
                    continue
                
                namespace_node = captures["namespace_def"][0]
                namespace_name_node = captures["namespace_name"][0]
                namespace_name = self._get_node_text(namespace_name_node, source)
                
                namespace_nodes.append((namespace_node, namespace_name))
                
        except Exception as e:
            logger.error(f"Failed to extract C# namespace nodes: {e}")
        
        return namespace_nodes
    
    def _extract_classes(self, tree_node: TSNode, source: str, 
                        file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# class definitions from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
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
                
                # Build qualified name with namespace
                qualified_name = class_name
                if namespace_name:
                    qualified_name = f"{namespace_name}.{class_name}"
                
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
                    "language": "csharp",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": class_text,
                    "start_byte": class_node.start_byte,
                    "end_byte": class_node.end_byte,
                }
                
                chunks.append(chunk)
                
                # Extract nested classes
                nested_chunks = self._extract_nested_classes(
                    class_node, source, file_path, qualified_name
                )
                chunks.extend(nested_chunks)
                
        except Exception as e:
            logger.error(f"Failed to extract C# classes: {e}")
        
        return chunks
    
    def _extract_interfaces(self, tree_node: TSNode, source: str,
                           file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# interface definitions from AST."""
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
                
                # Build qualified name with namespace
                qualified_name = interface_name
                if namespace_name:
                    qualified_name = f"{namespace_name}.{interface_name}"
                
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
                    "language": "csharp",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": interface_text,
                    "start_byte": interface_node.start_byte,
                    "end_byte": interface_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract C# interfaces: {e}")
        
        return chunks
    
    def _extract_structs(self, tree_node: TSNode, source: str,
                        file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# struct definitions from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (struct_declaration
                    name: (identifier) @struct_name
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
                
                # Build qualified name with namespace
                qualified_name = struct_name
                if namespace_name:
                    qualified_name = f"{namespace_name}.{struct_name}"
                
                # Check for generic type parameters
                type_params = self._extract_type_parameters(struct_node, source)
                if type_params:
                    display_name = f"{qualified_name}{type_params}"
                else:
                    display_name = qualified_name
                
                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": struct_node.start_point[0] + 1,
                    "end_line": struct_node.end_point[0] + 1,
                    "code": struct_text,
                    "chunk_type": ChunkType.STRUCT.value,
                    "language": "csharp",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": struct_text,
                    "start_byte": struct_node.start_byte,
                    "end_byte": struct_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract C# structs: {e}")
        
        return chunks
    
    def _extract_enums(self, tree_node: TSNode, source: str,
                      file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# enum definitions from AST."""
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
                
                # Build qualified name with namespace
                qualified_name = enum_name
                if namespace_name:
                    qualified_name = f"{namespace_name}.{enum_name}"
                
                # Create chunk
                chunk = {
                    "symbol": qualified_name,
                    "start_line": enum_node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "code": enum_text,
                    "chunk_type": ChunkType.ENUM.value,
                    "language": "csharp",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": qualified_name,
                    "content": enum_text,
                    "start_byte": enum_node.start_byte,
                    "end_byte": enum_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract C# enums: {e}")
        
        return chunks
    
    def _extract_methods(self, tree_node: TSNode, source: str,
                        file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# method definitions from AST."""
        method_chunks = []
        
        try:
            if self._language is None:
                return method_chunks
                
            # Find all classes and structs first to associate methods with their parents
            parent_query = self._language.query("""
                (class_declaration
                    name: (identifier) @class_name
                ) @class_def
                
                (struct_declaration
                    name: (identifier) @struct_name
                ) @struct_def
            """)
            
            parent_matches = parent_query.matches(tree_node)
            
            for match in parent_matches:
                pattern_index, captures = match
                parent_node = None
                parent_name = None
                
                if "class_def" in captures and "class_name" in captures:
                    parent_node = captures["class_def"][0]
                    parent_name_node = captures["class_name"][0]
                    parent_name = self._get_node_text(parent_name_node, source)
                elif "struct_def" in captures and "struct_name" in captures:
                    parent_node = captures["struct_def"][0]
                    parent_name_node = captures["struct_name"][0]
                    parent_name = self._get_node_text(parent_name_node, source)
                
                if not parent_node or not parent_name:
                    continue
                
                # Use qualified name with namespace
                qualified_parent_name = parent_name
                if namespace_name:
                    qualified_parent_name = f"{namespace_name}.{parent_name}"
                
                # Find the body node
                body_node = None
                for i in range(parent_node.child_count):
                    child = parent_node.child(i)
                    if child and child.type in ["declaration_list"]:
                        body_node = child
                        break
                        
                if not body_node:
                    continue
                    
                # Query for methods within the body
                if self._language is None:
                    continue
                        
                method_query = self._language.query("""
                    (method_declaration
                        name: (identifier) @method_name
                    ) @method_def
                    
                    (constructor_declaration) @constructor_def
                """)
                
                method_matches = method_query.matches(body_node)
                
                for method_match in method_matches:
                    pattern_index, captures = method_match
                    method_node = None
                    method_name = None
                    is_constructor = False
                    
                    if "method_def" in captures:
                        method_node = captures["method_def"][0]
                        if "method_name" in captures:
                            method_name_node = captures["method_name"][0]
                            method_name = self._get_node_text(method_name_node, source)
                    elif "constructor_def" in captures:
                        method_node = captures["constructor_def"][0]
                        method_name = parent_name  # Constructor has same name as class
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
                    qualified_name = f"{qualified_parent_name}.{method_name}"
                    display_name = f"{qualified_name}({param_types_str})"
                    
                    # Check for generic type parameters
                    type_params = self._extract_type_parameters(method_node, source)
                    if type_params:
                        display_name = f"{qualified_name}{type_params}({param_types_str})"
                    
                    # Create chunk
                    chunk_type_enum = ChunkType.CONSTRUCTOR if is_constructor else ChunkType.METHOD
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": method_node.start_point[0] + 1,
                        "end_line": method_node.end_point[0] + 1,
                        "code": method_text,
                        "chunk_type": chunk_type_enum.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": method_text,
                        "start_byte": method_node.start_byte,
                        "end_byte": method_node.end_byte,
                        "parent": qualified_parent_name,
                        "parameters": parameters,
                    }
                    
                    if return_type and not is_constructor:
                        chunk["return_type"] = return_type
                    
                    method_chunks.append(chunk)
            
        except Exception as e:
            logger.error(f"Failed to extract C# methods: {e}")
        
        return method_chunks
    
    def _extract_nested_classes(self, parent_node: TSNode, source: str,
                               file_path: Path, parent_qualified_name: str) -> List[Dict[str, Any]]:
        """Extract nested C# class definitions from within a parent class."""
        chunks = []
        
        try:
            # Find the declaration list
            body_node = None
            for i in range(parent_node.child_count):
                child = parent_node.child(i)
                if child and child.type == "declaration_list":
                    body_node = child
                    break
            
            if not body_node:
                return chunks
            
            # Query for nested classes
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (class_declaration
                    name: (identifier) @nested_class_name
                ) @nested_class_def
            """)
            
            matches = query.matches(body_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "nested_class_def" not in captures or "nested_class_name" not in captures:
                    continue
                
                nested_class_node = captures["nested_class_def"][0]
                nested_class_name_node = captures["nested_class_name"][0]
                nested_class_name = self._get_node_text(nested_class_name_node, source)
                
                nested_text = self._get_node_text(nested_class_node, source)
                nested_qualified_name = f"{parent_qualified_name}.{nested_class_name}"
                
                type_params = self._extract_type_parameters(nested_class_node, source)
                if type_params:
                    display_name = f"{nested_qualified_name}{type_params}"
                else:
                    display_name = nested_qualified_name
                
                chunk = {
                    "symbol": nested_qualified_name,
                    "start_line": nested_class_node.start_point[0] + 1,
                    "end_line": nested_class_node.end_point[0] + 1,
                    "code": nested_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "csharp",
                    "path": str(file_path),
                    "name": nested_qualified_name,
                    "display_name": display_name,
                    "content": nested_text,
                    "start_byte": nested_class_node.start_byte,
                    "end_byte": nested_class_node.end_byte,
                    "parent": parent_qualified_name,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract C# nested classes: {e}")
        
        return chunks
    
    def _extract_type_parameters(self, node: TSNode, source: str) -> str:
        """Extract C# generic type parameters from a node."""
        try:
            if self._language is None:
                return ""
                
            # Look for type_parameter_list node as a child
            for i in range(node.child_count):
                child = node.child(i)
                if child and child.type == "type_parameter_list":
                    return self._get_node_text(child, source).strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to extract C# type parameters: {e}")
            return ""
    
    def _extract_method_parameters(self, method_node: TSNode, source: str) -> List[str]:
        """Extract parameter types from a C# method."""
        parameters = []
        
        try:
            if self._language is None:
                return parameters
                
            # Find the parameter list node
            params_node = None
            for i in range(method_node.child_count):
                child = method_node.child(i)
                if child and child.type == "parameter_list":
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
            logger.error(f"Failed to extract C# method parameters: {e}")
        
        return parameters
    
    def _extract_method_return_type(self, method_node: TSNode, source: str) -> Optional[str]:
        """Extract return type from a C# method."""
        try:
            if self._language is None:
                return None
                
            # Find the return type node
            type_node = method_node.child_by_field_name("type")
            if type_node:
                return self._get_node_text(type_node, source).strip()
            return None
        except Exception as e:
            logger.error(f"Failed to extract C# method return type: {e}")
            return None