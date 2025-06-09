"""TypeScript language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    from tree_sitter_language_pack import get_language, get_parser
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    TYPESCRIPT_AVAILABLE = True
except ImportError:
    TYPESCRIPT_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class TypeScriptParser:
    """TypeScript language parser using tree-sitter."""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize TypeScript parser.
        
        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False
        
        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.TYPESCRIPT,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.INTERFACE,
                ChunkType.METHOD,
                ChunkType.ENUM,
                ChunkType.TYPE_ALIAS,
                ChunkType.FUNCTION
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
        if TYPESCRIPT_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize the TypeScript parser.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not TYPESCRIPT_AVAILABLE:
            logger.error("TypeScript tree-sitter support not available")
            return False
        
        try:
            if get_language and get_parser:
                self._language = get_language('typescript')
                self._parser = get_parser('typescript')
                self._initialized = True
                logger.debug("TypeScript parser initialized successfully")
                return True
            else:
                logger.error("TypeScript parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize TypeScript parser: {e}")
            return False
    
    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.TYPESCRIPT
    
    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types
    
    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return TYPESCRIPT_AVAILABLE and self._initialized
    
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a TypeScript file and extract semantic chunks.
        
        Args:
            file_path: Path to TypeScript file
            source: Optional source code string
            
        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []
        
        if not self.is_available:
            errors.append("TypeScript parser not available")
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
                errors.append("TypeScript parser not initialized")
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
            
            # Extract semantic units
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_functions(tree.root_node, source, file_path))
            
            if ChunkType.CLASS in self._config.chunk_types:
                chunks.extend(self._extract_classes(tree.root_node, source, file_path))
            
            if ChunkType.INTERFACE in self._config.chunk_types:
                chunks.extend(self._extract_interfaces(tree.root_node, source, file_path))
            
            if ChunkType.ENUM in self._config.chunk_types:
                chunks.extend(self._extract_enums(tree.root_node, source, file_path))
            
            if ChunkType.TYPE_ALIAS in self._config.chunk_types:
                chunks.extend(self._extract_type_aliases(tree.root_node, source, file_path))
            
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_components(tree.root_node, source, file_path))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to parse TypeScript file {file_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        return ParseResult(
            chunks=chunks,
            language=self.language,
            total_chunks=len(chunks),
            parse_time=time.time() - start_time,
            errors=errors,
            warnings=warnings,
            metadata={"file_path": str(file_path)}
        )
    
    def _get_node_text(self, node: TSNode, source: str) -> str:
        """Extract text content from a tree-sitter node."""
        return source[node.start_byte:node.end_byte]
    
    def _extract_functions(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript function declarations from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (function_declaration
                    name: (identifier) @function_name
                ) @function_def
                
                (arrow_function) @arrow_function_def
                
                (function_expression
                    name: (identifier) @function_name
                ) @function_expr_def
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                function_node = None
                function_name = None
                
                if "function_def" in captures:
                    function_node = captures["function_def"][0]
                    if "function_name" in captures:
                        function_name_node = captures["function_name"][0]
                        function_name = self._get_node_text(function_name_node, source)
                elif "arrow_function_def" in captures:
                    function_node = captures["arrow_function_def"][0]
                    function_name = "anonymous_arrow_function"
                elif "function_expr_def" in captures:
                    function_node = captures["function_expr_def"][0]
                    if "function_name" in captures:
                        function_name_node = captures["function_name"][0]
                        function_name = self._get_node_text(function_name_node, source)
                
                if not function_node or not function_name:
                    continue
                
                function_text = self._get_node_text(function_node, source)
                
                # Extract parameters
                parameters = self._extract_function_parameters(function_node, source)
                param_types_str = ", ".join(parameters)
                
                # Extract return type
                return_type = self._extract_function_return_type(function_node, source)
                
                display_name = f"{function_name}({param_types_str})"
                if return_type:
                    display_name += f": {return_type}"
                
                chunk = {
                    "symbol": function_name,
                    "start_line": function_node.start_point[0] + 1,
                    "end_line": function_node.end_point[0] + 1,
                    "code": function_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": function_name,
                    "display_name": display_name,
                    "content": function_text,
                    "start_byte": function_node.start_byte,
                    "end_byte": function_node.end_byte,
                    "parameters": parameters,
                }
                
                if return_type:
                    chunk["return_type"] = return_type
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript functions: {e}")
        
        return chunks
    
    def _extract_classes(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript class declarations from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (class_declaration
                    name: (type_identifier) @class_name
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
                
                class_text = self._get_node_text(class_node, source)
                
                # Extract type parameters
                type_params = self._extract_type_parameters(class_node, source)
                if type_params:
                    display_name = f"{class_name}{type_params}"
                else:
                    display_name = class_name
                
                chunk = {
                    "symbol": class_name,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": class_name,
                    "display_name": display_name,
                    "content": class_text,
                    "start_byte": class_node.start_byte,
                    "end_byte": class_node.end_byte,
                }
                
                chunks.append(chunk)
                
                # Extract methods from class
                if ChunkType.METHOD in self._config.chunk_types:
                    method_chunks = self._extract_class_methods(class_node, source, file_path, class_name)
                    chunks.extend(method_chunks)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript classes: {e}")
        
        return chunks
    
    def _extract_interfaces(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript interface declarations from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (interface_declaration
                    name: (type_identifier) @interface_name
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
                
                interface_text = self._get_node_text(interface_node, source)
                
                # Extract type parameters
                type_params = self._extract_type_parameters(interface_node, source)
                if type_params:
                    display_name = f"{interface_name}{type_params}"
                else:
                    display_name = interface_name
                
                chunk = {
                    "symbol": interface_name,
                    "start_line": interface_node.start_point[0] + 1,
                    "end_line": interface_node.end_point[0] + 1,
                    "code": interface_text,
                    "chunk_type": ChunkType.INTERFACE.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": interface_name,
                    "display_name": display_name,
                    "content": interface_text,
                    "start_byte": interface_node.start_byte,
                    "end_byte": interface_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript interfaces: {e}")
        
        return chunks
    
    def _extract_enums(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript enum declarations from AST."""
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
                
                enum_text = self._get_node_text(enum_node, source)
                
                chunk = {
                    "symbol": enum_name,
                    "start_line": enum_node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "code": enum_text,
                    "chunk_type": ChunkType.ENUM.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": enum_name,
                    "display_name": enum_name,
                    "content": enum_text,
                    "start_byte": enum_node.start_byte,
                    "end_byte": enum_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript enums: {e}")
        
        return chunks
    
    def _extract_type_aliases(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript type alias declarations from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (type_alias_declaration
                    name: (type_identifier) @type_name
                ) @type_def
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "type_def" not in captures or "type_name" not in captures:
                    continue
                
                type_node = captures["type_def"][0]
                type_name_node = captures["type_name"][0]
                type_name = self._get_node_text(type_name_node, source)
                
                type_text = self._get_node_text(type_node, source)
                
                # Extract type parameters
                type_params = self._extract_type_parameters(type_node, source)
                if type_params:
                    display_name = f"{type_name}{type_params}"
                else:
                    display_name = type_name
                
                chunk = {
                    "symbol": type_name,
                    "start_line": type_node.start_point[0] + 1,
                    "end_line": type_node.end_point[0] + 1,
                    "code": type_text,
                    "chunk_type": ChunkType.TYPE_ALIAS.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": type_name,
                    "display_name": display_name,
                    "content": type_text,
                    "start_byte": type_node.start_byte,
                    "end_byte": type_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript type aliases: {e}")
        
        return chunks
    
    def _extract_components(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract React component declarations from TypeScript/TSX."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            # Look for function components (functions returning JSX)
            query = self._language.query("""
                (function_declaration
                    name: (identifier) @component_name
                    return_type: (type_annotation
                        type: (type_identifier) @return_type
                    )?
                ) @component_def
                
                (variable_declarator
                    name: (identifier) @component_name
                    value: (arrow_function) @arrow_component
                ) @var_component
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                component_node = None
                component_name = None
                
                if "component_def" in captures and "component_name" in captures:
                    component_node = captures["component_def"][0]
                    component_name_node = captures["component_name"][0]
                    component_name = self._get_node_text(component_name_node, source)
                    
                    # Check if it's likely a React component (starts with capital letter)
                    if not component_name[0].isupper():
                        continue
                        
                elif "var_component" in captures and "component_name" in captures:
                    component_node = captures["var_component"][0]
                    component_name_node = captures["component_name"][0]
                    component_name = self._get_node_text(component_name_node, source)
                    
                    # Check if it's likely a React component (starts with capital letter)
                    if not component_name[0].isupper():
                        continue
                
                if not component_node or not component_name:
                    continue
                
                component_text = self._get_node_text(component_node, source)
                
                # Extract props parameters
                parameters = self._extract_function_parameters(component_node, source)
                param_types_str = ", ".join(parameters)
                
                display_name = f"{component_name}({param_types_str})"
                
                chunk = {
                    "symbol": component_name,
                    "start_line": component_node.start_point[0] + 1,
                    "end_line": component_node.end_point[0] + 1,
                    "code": component_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": component_name,
                    "display_name": display_name,
                    "content": component_text,
                    "start_byte": component_node.start_byte,
                    "end_byte": component_node.end_byte,
                    "parameters": parameters,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript components: {e}")
        
        return chunks
    
    def _extract_class_methods(self, class_node: TSNode, source: str, 
                              file_path: Path, class_name: str) -> List[Dict[str, Any]]:
        """Extract methods from a TypeScript class."""
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
            
            # Query for methods within the class body
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (method_definition
                    name: (property_name) @method_name
                ) @method_def
                
                (method_signature
                    name: (property_name) @method_name
                ) @method_sig
            """)
            
            matches = query.matches(body_node)
            
            for match in matches:
                pattern_index, captures = match
                method_node = None
                method_name = None
                
                if "method_def" in captures and "method_name" in captures:
                    method_node = captures["method_def"][0]
                    method_name_node = captures["method_name"][0]
                    method_name = self._get_node_text(method_name_node, source)
                elif "method_sig" in captures and "method_name" in captures:
                    method_node = captures["method_sig"][0]
                    method_name_node = captures["method_name"][0]
                    method_name = self._get_node_text(method_name_node, source)
                
                if not method_node or not method_name:
                    continue
                
                method_text = self._get_node_text(method_node, source)
                
                # Extract parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_types_str = ", ".join(parameters)
                
                # Extract return type
                return_type = self._extract_function_return_type(method_node, source)
                
                qualified_name = f"{class_name}.{method_name}"
                display_name = f"{qualified_name}({param_types_str})"
                if return_type:
                    display_name += f": {return_type}"
                
                chunk = {
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "typescript",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parent": class_name,
                    "parameters": parameters,
                }
                
                if return_type:
                    chunk["return_type"] = return_type
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract TypeScript class methods: {e}")
        
        return chunks
    
    def _extract_type_parameters(self, node: TSNode, source: str) -> str:
        """Extract generic type parameters from a TypeScript node."""
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
            logger.error(f"Failed to extract TypeScript type parameters: {e}")
            return ""
    
    def _extract_function_parameters(self, function_node: TSNode, source: str) -> List[str]:
        """Extract parameter types from a TypeScript function."""
        parameters = []
        
        try:
            if self._language is None:
                return parameters
                
            # Find the parameters node
            params_node = None
            for i in range(function_node.child_count):
                child = function_node.child(i)
                if child and child.type in ["formal_parameters", "parameters"]:
                    params_node = child
                    break
                    
            if not params_node:
                return parameters
                
            # Extract each parameter
            for i in range(params_node.child_count):
                child = params_node.child(i)
                if child and child.type in ["required_parameter", "optional_parameter"]:
                    # Get parameter with type annotation
                    param_text = self._get_node_text(child, source).strip()
                    if param_text and param_text != "," and param_text != "(" and param_text != ")":
                        parameters.append(param_text)
                        
        except Exception as e:
            logger.error(f"Failed to extract TypeScript function parameters: {e}")
        
        return parameters
    
    def _extract_function_return_type(self, function_node: TSNode, source: str) -> Optional[str]:
        """Extract return type from a TypeScript function."""
        try:
            if self._language is None:
                return None
            # Look for type annotation
            for i in range(function_node.child_count):
                child = function_node.child(i)
                if child and child.type == "type_annotation":
                    return self._get_node_text(child, source).strip()
            return None
        except Exception as e:
            logger.error(f"Failed to extract TypeScript function return type: {e}")
            return None