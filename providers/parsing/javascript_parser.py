"""JavaScript language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    from tree_sitter_language_pack import get_language, get_parser
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    JAVASCRIPT_AVAILABLE = True
except ImportError:
    JAVASCRIPT_AVAILABLE = False
    get_language = None
    get_parser = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class JavaScriptParser:
    """JavaScript language parser using tree-sitter."""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize JavaScript parser.
        
        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False
        
        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.JAVASCRIPT,
            chunk_types={
                ChunkType.FUNCTION,
                ChunkType.CLASS,
                ChunkType.METHOD
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
        if JAVASCRIPT_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize the JavaScript parser.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not JAVASCRIPT_AVAILABLE:
            logger.error("JavaScript tree-sitter support not available")
            return False
        
        try:
            if get_language and get_parser:
                self._language = get_language('javascript')
                self._parser = get_parser('javascript')
                self._initialized = True
                logger.debug("JavaScript parser initialized successfully")
                return True
            else:
                logger.error("JavaScript parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize JavaScript parser: {e}")
            return False
    
    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.JAVASCRIPT
    
    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types
    
    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return JAVASCRIPT_AVAILABLE and self._initialized
    
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a JavaScript file and extract semantic chunks.
        
        Args:
            file_path: Path to JavaScript file
            source: Optional source code string
            
        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []
        
        if not self.is_available:
            errors.append("JavaScript parser not available")
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
                errors.append("JavaScript parser not initialized")
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
            
            if ChunkType.FUNCTION in self._config.chunk_types:
                chunks.extend(self._extract_components(tree.root_node, source, file_path))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to parse JavaScript file {file_path}: {e}"
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
        """Extract JavaScript function declarations from AST."""
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
                
                (variable_declarator
                    name: (identifier) @var_name
                    value: (arrow_function) @arrow_func
                ) @var_function
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
                elif "var_function" in captures and "var_name" in captures:
                    function_node = captures["var_function"][0]
                    var_name_node = captures["var_name"][0]
                    function_name = self._get_node_text(var_name_node, source)
                
                if not function_node or not function_name:
                    continue
                
                function_text = self._get_node_text(function_node, source)
                
                # Extract parameters
                parameters = self._extract_function_parameters(function_node, source)
                param_str = ", ".join(parameters)
                
                display_name = f"{function_name}({param_str})"
                
                chunk = {
                    "symbol": function_name,
                    "start_line": function_node.start_point[0] + 1,
                    "end_line": function_node.end_point[0] + 1,
                    "code": function_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "javascript",
                    "path": str(file_path),
                    "name": function_name,
                    "display_name": display_name,
                    "content": function_text,
                    "start_byte": function_node.start_byte,
                    "end_byte": function_node.end_byte,
                    "parameters": parameters,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract JavaScript functions: {e}")
        
        return chunks
    
    def _extract_classes(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract JavaScript class declarations from AST."""
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
                
                class_text = self._get_node_text(class_node, source)
                
                chunk = {
                    "symbol": class_name,
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "javascript",
                    "path": str(file_path),
                    "name": class_name,
                    "display_name": class_name,
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
            logger.error(f"Failed to extract JavaScript classes: {e}")
        
        return chunks
    
    def _extract_components(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract React component declarations from JavaScript/JSX."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            # Look for function components (functions returning JSX)
            query = self._language.query("""
                (function_declaration
                    name: (identifier) @component_name
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
                param_str = ", ".join(parameters)
                
                display_name = f"{component_name}({param_str})"
                
                chunk = {
                    "symbol": component_name,
                    "start_line": component_node.start_point[0] + 1,
                    "end_line": component_node.end_point[0] + 1,
                    "code": component_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language": "javascript",
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
            logger.error(f"Failed to extract JavaScript components: {e}")
        
        return chunks
    
    def _extract_class_methods(self, class_node: TSNode, source: str, 
                              file_path: Path, class_name: str) -> List[Dict[str, Any]]:
        """Extract methods from a JavaScript class."""
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
            """)
            
            matches = query.matches(body_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "method_def" not in captures or "method_name" not in captures:
                    continue
                
                method_node = captures["method_def"][0]
                method_name_node = captures["method_name"][0]
                method_name = self._get_node_text(method_name_node, source)
                
                method_text = self._get_node_text(method_node, source)
                
                # Extract parameters
                parameters = self._extract_function_parameters(method_node, source)
                param_str = ", ".join(parameters)
                
                qualified_name = f"{class_name}.{method_name}"
                display_name = f"{qualified_name}({param_str})"
                
                chunk = {
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "javascript",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
                    "start_byte": method_node.start_byte,
                    "end_byte": method_node.end_byte,
                    "parent": class_name,
                    "parameters": parameters,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract JavaScript class methods: {e}")
        
        return chunks
    
    def _extract_function_parameters(self, function_node: TSNode, source: str) -> List[str]:
        """Extract parameter names from a JavaScript function."""
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
                if child and child.type == "identifier":
                    param_name = self._get_node_text(child, source).strip()
                    if param_name and param_name != "," and param_name != "(" and param_name != ")":
                        parameters.append(param_name)
                elif child and child.type == "assignment_pattern":
                    # Handle default parameters
                    left_child = child.child(0)
                    if left_child and left_child.type == "identifier":
                        param_name = self._get_node_text(left_child, source).strip()
                        if param_name:
                            parameters.append(param_name)
                        
        except Exception as e:
            logger.error(f"Failed to extract JavaScript function parameters: {e}")
        
        return parameters