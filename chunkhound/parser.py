"""Code parser module for ChunkHound - tree-sitter integration for Python AST parsing."""

from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from tree_sitter import Language, Parser, Node, Tree
    TreeSitterLanguage = Language
    TreeSitterParser = Parser
    TreeSitterNode = Node
    TreeSitterTree = Tree
else:
    TreeSitterLanguage = Any
    TreeSitterParser = Any
    TreeSitterNode = Any
    TreeSitterTree = Any

try:
    from tree_sitter import Node
    from tree_sitter_language_pack import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
    PYTHON_AVAILABLE = True
    MARKDOWN_AVAILABLE = True
    JAVA_AVAILABLE = True
    CSHARP_AVAILABLE = True
    TYPESCRIPT_AVAILABLE = True
    JAVASCRIPT_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    PYTHON_AVAILABLE = False
    MARKDOWN_AVAILABLE = False
    JAVA_AVAILABLE = False
    CSHARP_AVAILABLE = False
    TYPESCRIPT_AVAILABLE = False
    JAVASCRIPT_AVAILABLE = False
    Node = None
    get_language = None
    get_parser = None

from loguru import logger

# Core domain types
from core.types import ChunkType, Language
from .tree_cache import get_default_cache, TreeCache


def is_tree_sitter_node(obj: Any) -> bool:
    """Check if object is a valid TreeSitterNode with required attributes."""
    return (obj is not None and 
            hasattr(obj, 'start_byte') and 
            hasattr(obj, 'end_byte') and 
            hasattr(obj, 'id'))


class CodeParser:
    """Tree-sitter based code parser for extracting semantic units."""
    
    def __init__(self, use_cache: bool = True, cache: Optional[TreeCache] = None):
        """Initialize the code parser.
        
        Args:
            use_cache: Whether to use TreeCache for performance optimization
            cache: Custom TreeCache instance, uses default if None
        """
        self.python_language: Optional[TreeSitterLanguage] = None
        self.python_parser: Optional[TreeSitterParser] = None
        self.markdown_language: Optional[TreeSitterLanguage] = None
        self.markdown_parser: Optional[TreeSitterParser] = None
        self.java_language: Optional[TreeSitterLanguage] = None
        self.java_parser: Optional[TreeSitterParser] = None
        self.csharp_language: Optional[TreeSitterLanguage] = None
        self.csharp_parser: Optional[TreeSitterParser] = None
        self.typescript_language: Optional[TreeSitterLanguage] = None
        self.typescript_parser: Optional[TreeSitterParser] = None
        self.javascript_language: Optional[TreeSitterLanguage] = None
        self.javascript_parser: Optional[TreeSitterParser] = None
        self.tsx_language: Optional[TreeSitterLanguage] = None
        self.tsx_parser: Optional[TreeSitterParser] = None
        self._python_initialized = False
        self._markdown_initialized = False
        self._java_initialized = False
        self._csharp_initialized = False
        self._typescript_initialized = False
        self._javascript_initialized = False
        self._tsx_initialized = False
        
        # TreeCache integration
        self.use_cache = use_cache
        self.tree_cache = cache or get_default_cache() if use_cache else None
        
    def setup(self) -> None:
        """Set up tree-sitter parsers for Python, Markdown, Java, C#, TypeScript, and JavaScript."""
        if not TREE_SITTER_AVAILABLE:
            logger.error("Tree-sitter dependencies not available")
            return
            
        logger.info("Setting up tree-sitter parsers")
        
        # Setup Python parser
        if PYTHON_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.python_language = get_language('python')
                self.python_parser = get_parser('python')
                self._python_initialized = True
                logger.info("Python parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Python parser: {e}")
                self._python_initialized = False
        else:
            logger.warning("Python parser not available - tree_sitter_language_pack not installed")
            
        # Setup Markdown parser
        if MARKDOWN_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.markdown_language = get_language('markdown')
                self.markdown_parser = get_parser('markdown')
                self._markdown_initialized = True
                logger.info("Markdown parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Markdown parser: {e}")
                self._markdown_initialized = False
        else:
            logger.warning("Markdown parser not available - tree_sitter_language_pack not installed")
            
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
            
        # Setup C# parser
        if CSHARP_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.csharp_language = get_language('csharp')
                self.csharp_parser = get_parser('csharp')
                self._csharp_initialized = True
                logger.info("C# parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize C# parser: {e}")
                self._csharp_initialized = False
        else:
            logger.warning("C# parser not available - tree_sitter_language_pack not installed")
            
        # Setup TypeScript parser
        if TYPESCRIPT_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.typescript_language = get_language('typescript')
                self.typescript_parser = get_parser('typescript')
                self._typescript_initialized = True
                logger.info("TypeScript parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize TypeScript parser: {e}")
                self._typescript_initialized = False
        else:
            logger.warning("TypeScript parser not available - tree_sitter_language_pack not installed")
            
        # Setup JavaScript parser
        if JAVASCRIPT_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.javascript_language = get_language('javascript')
                self.javascript_parser = get_parser('javascript')
                self._javascript_initialized = True
                logger.info("JavaScript parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize JavaScript parser: {e}")
                self._javascript_initialized = False
        else:
            logger.warning("JavaScript parser not available - tree_sitter_language_pack not installed")
            
        # Setup TSX parser
        if TYPESCRIPT_AVAILABLE and get_language is not None and get_parser is not None:
            try:
                self.tsx_language = get_language('tsx')
                self.tsx_parser = get_parser('tsx')
                self._tsx_initialized = True
                logger.info("TSX parser initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize TSX parser: {e}")
                self._tsx_initialized = False
        else:
            logger.warning("TSX parser not available - tree_sitter_language_pack not installed")
        
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a file and extract semantic chunks.
        
        Args:
            file_path: Path to file to parse
            source: Optional source code string (if None, reads from file)
            
        Returns:
            List of extracted chunks with metadata
        """
        # Determine file type using core Language enum
        language = Language.from_file_extension(file_path)
        
        if language == Language.PYTHON:
            return self._parse_python_file(file_path, source)
        elif language == Language.MARKDOWN:
            return self._parse_markdown_file(file_path, source)
        elif language == Language.JAVA:
            return self._parse_java_file(file_path, source)
        elif language == Language.CSHARP:
            return self._parse_csharp_file(file_path, source)
        elif language == Language.TYPESCRIPT:
            return self._parse_typescript_file(file_path, source)
        elif language == Language.JAVASCRIPT:
            return self._parse_javascript_file(file_path, source)
        elif language == Language.TSX:
            return self._parse_tsx_file(file_path, source)
        elif language == Language.JSX:
            return self._parse_jsx_file(file_path, source)
        else:
            logger.warning(f"Unsupported file type: {file_path.suffix}")
            return []
    
    def _extract_csharp_structs(self, tree_node: TreeSitterNode, source_code: str,
                               file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# struct definitions from AST.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            file_path: Path to the C# file
            namespace_name: Namespace name for context
            
        Returns:
            List of struct chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (struct_declaration name: (identifier) @struct_name) @struct_def
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                struct_node = None
                struct_name = None
                
                # Get struct definition node
                if "struct_def" in captures:
                    struct_node = captures["struct_def"][0]  # Take first match
                    
                # Get struct name
                if "struct_name" in captures:
                    struct_name_node = captures["struct_name"][0]  # Take first match
                    struct_name = self._get_node_text(struct_name_node, source_code).strip()
                
                if struct_node and struct_name:
                    start_line = struct_node.start_point[0] + 1
                    end_line = struct_node.end_point[0] + 1
                    
                    # Build qualified struct name
                    qualified_name = f"{namespace_name}.{struct_name}" if namespace_name else struct_name
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(struct_node, source_code),
                        "chunk_type": ChunkType.STRUCT.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(struct_node, source_code),
                        "start_byte": struct_node.start_byte,
                        "end_byte": struct_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# struct: {qualified_name} at lines {start_line}-{end_line}")
                    
                    # Extract properties within this struct
                    property_chunks = self._extract_csharp_properties(struct_node, source_code, file_path, qualified_name)
                    chunks.extend(property_chunks)
                    
                    # Extract constructors within this struct
                    constructor_chunks = self._extract_csharp_constructors(struct_node, source_code, file_path, qualified_name)
                    chunks.extend(constructor_chunks)
                    
        except Exception as e:
            logger.error(f"Failed to extract C# structs: {e}")
            
        return chunks
    
    def _extract_csharp_enums(self, tree_node: TreeSitterNode, source_code: str,
                             file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# enum definitions from AST.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            file_path: Path to the C# file
            namespace_name: Namespace name for context
            
        Returns:
            List of enum chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (enum_declaration name: (identifier) @enum_name) @enum_def
            """)
            
            matches = query.matches(tree_node)
            
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
                    enum_name = self._get_node_text(enum_name_node, source_code).strip()
                
                if enum_node and enum_name:
                    start_line = enum_node.start_point[0] + 1
                    end_line = enum_node.end_point[0] + 1
                    
                    # Build qualified enum name
                    qualified_name = f"{namespace_name}.{enum_name}" if namespace_name else enum_name
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(enum_node, source_code),
                        "chunk_type": ChunkType.ENUM.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(enum_node, source_code),
                        "start_byte": enum_node.start_byte,
                        "end_byte": enum_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# enum: {qualified_name} at lines {start_line}-{end_line}")
                    
        except Exception as e:
            logger.error(f"Failed to extract C# enums: {e}")
            
        return chunks
    
    def _extract_csharp_properties(self, parent_node: TreeSitterNode, source_code: str,
                                  file_path: Path, parent_name: str) -> List[Dict[str, Any]]:
        """Extract C# property definitions from a class or struct.
        
        Args:
            parent_node: Parent class or struct node
            source_code: Source code content
            file_path: Path to the C# file
            parent_name: Qualified name of parent class/struct
            
        Returns:
            List of property chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (property_declaration name: (identifier) @property_name) @property_def
            """)
            
            matches = query.matches(parent_node)
            
            for match in matches:
                pattern_index, captures = match
                property_node = None
                property_name = None
                
                # Get property definition node
                if "property_def" in captures:
                    property_node = captures["property_def"][0]  # Take first match
                    
                # Get property name
                if "property_name" in captures:
                    property_name_node = captures["property_name"][0]  # Take first match
                    property_name = self._get_node_text(property_name_node, source_code).strip()
                
                if property_node and property_name:
                    start_line = property_node.start_point[0] + 1
                    end_line = property_node.end_point[0] + 1
                    
                    # Build qualified property name
                    qualified_name = f"{parent_name}.{property_name}"
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(property_node, source_code),
                        "chunk_type": ChunkType.PROPERTY.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(property_node, source_code),
                        "start_byte": property_node.start_byte,
                        "end_byte": property_node.end_byte,
                        "parent": parent_name,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# property: {qualified_name} at lines {start_line}-{end_line}")
                    
        except Exception as e:
            logger.error(f"Failed to extract C# properties: {e}")
            
        return chunks
    
    def _extract_csharp_constructors(self, parent_node: TreeSitterNode, source_code: str,
                                    file_path: Path, parent_name: str) -> List[Dict[str, Any]]:
        """Extract C# constructor definitions from a class or struct.
        
        Args:
            parent_node: Parent class or struct node
            source_code: Source code content
            file_path: Path to the C# file
            parent_name: Qualified name of parent class/struct
            
        Returns:
            List of constructor chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (constructor_declaration name: (identifier) @constructor_name) @constructor_def
            """)
            
            matches = query.matches(parent_node)
            
            for match in matches:
                pattern_index, captures = match
                constructor_node = None
                constructor_name = None
                
                # Get constructor definition node
                if "constructor_def" in captures:
                    constructor_node = captures["constructor_def"][0]  # Take first match
                    
                # Get constructor name
                if "constructor_name" in captures:
                    constructor_name_node = captures["constructor_name"][0]  # Take first match
                    constructor_name = self._get_node_text(constructor_name_node, source_code).strip()
                
                if constructor_node and constructor_name:
                    start_line = constructor_node.start_point[0] + 1
                    end_line = constructor_node.end_point[0] + 1
                    
                    # Extract parameters for constructor signature
                    parameters = self._extract_csharp_constructor_parameters(constructor_node, source_code)
                    param_str = ", ".join(parameters) if parameters else ""
                    
                    # Build qualified constructor name with parameters
                    qualified_name = f"{parent_name}.{constructor_name}({param_str})"
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(constructor_node, source_code),
                        "chunk_type": ChunkType.CONSTRUCTOR.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(constructor_node, source_code),
                        "start_byte": constructor_node.start_byte,
                        "end_byte": constructor_node.end_byte,
                        "parent": parent_name,
                        "parameters": parameters
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# constructor: {qualified_name} at lines {start_line}-{end_line}")
                    
        except Exception as e:
            logger.error(f"Failed to extract C# constructors: {e}")
            
        return chunks
    
    def _extract_csharp_constructor_parameters(self, constructor_node: TreeSitterNode, source_code: str) -> List[str]:
        """Extract parameter types from a C# constructor.
        
        Args:
            constructor_node: Constructor AST node
            source_code: Source code content
            
        Returns:
            List of parameter type strings
        """
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("(parameter) @param")
            
            matches = query.matches(constructor_node)
            param_types = []
            
            for match in matches:
                pattern_index, captures = match
                if "param" in captures:
                    param_node = captures["param"][0]
                    # Extract type from parameter node
                    for child in param_node.children:
                        if child.type in ["predefined_type", "identifier", "generic_name"]:
                            param_type = self._get_node_text(child, source_code).strip()
                            param_types.append(param_type)
                            break
                    
            return param_types
            
        except Exception as e:
            logger.error(f"Failed to extract constructor parameters: {e}")
            return []
    
    def parse_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse file incrementally using TreeCache for performance optimization.
        
        This method uses cached syntax trees when possible to achieve 10-100x
        performance improvement over full parsing for unchanged files.
        
        Args:
            file_path: Path to file to parse
            source: Optional source code string (if None, reads from file)
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self.use_cache:
            # Fallback to regular parsing if caching disabled
            return self.parse_file(file_path, source)
        
        logger.debug(f"Incremental parsing: {file_path}")
        
        # Determine file type
        suffix = file_path.suffix.lower()
        
        if suffix == '.py':
            return self._parse_python_file_incremental(file_path, source)
        elif suffix in ['.md', '.markdown']:
            return self._parse_markdown_file_incremental(file_path, source)
        elif suffix == '.java':
            return self._parse_java_file_incremental(file_path, source)
        elif suffix == '.cs':
            return self._parse_csharp_file_incremental(file_path, source)
        elif suffix == '.ts':
            return self._parse_typescript_file_incremental(file_path, source)
        elif suffix == '.js':
            return self._parse_javascript_file_incremental(file_path, source)
        elif suffix == '.tsx':
            return self._parse_tsx_file_incremental(file_path, source)
        elif suffix == '.jsx':
            return self._parse_jsx_file_incremental(file_path, source)
        else:
            logger.warning(f"Unsupported file type for incremental parsing: {suffix}")
            return []
    
    def parse_incremental(self, file_path: Path, source: Optional[str] = None) -> Optional[TreeSitterTree]:
        """Parse file using TreeCache for performance optimization.
        
        Args:
            file_path: Path to file to parse
            source: Optional source code string (if None, reads from file)
            
        Returns:
            Parsed syntax tree, or None if parsing failed
        """
        if not self.use_cache:
            return self._parse_tree_only(file_path, source)
        
        # Check cache first
        if self.tree_cache is not None:
            cached_tree = self.tree_cache.get(file_path)
            if cached_tree:
                logger.debug(f"TreeCache hit for {file_path}")
                return cached_tree
        
        # Cache miss - parse and store
        logger.debug(f"TreeCache miss for {file_path}")
        tree = self._parse_tree_only(file_path, source)
        if tree and self.tree_cache is not None:
            self.tree_cache.put(file_path, tree)
        return tree
    
    def invalidate_cache(self, file_path: Path) -> bool:
        """Invalidate cached tree for file.
        
        Args:
            file_path: Path to source file
            
        Returns:
            True if entry was found and removed, False otherwise
        """
        if self.tree_cache:
            return self.tree_cache.invalidate(file_path)
        return False
    
    def get_changed_regions(self, old_tree: TreeSitterTree, new_tree: TreeSitterTree) -> List[Dict[str, Any]]:
        """Compare syntax trees and return changed regions for differential updates.
        
        Args:
            old_tree: Previous syntax tree
            new_tree: New syntax tree
            
        Returns:
            List of changed regions with start/end positions
        """
        if old_tree is None or new_tree is None:
            return [{'start_byte': 0, 'end_byte': float('inf'), 'type': 'full_change'}]
        
        # Simple implementation: compare root node ranges
        # In a more sophisticated implementation, we would do deep tree comparison
        old_root = old_tree.root_node
        new_root = new_tree.root_node
        
        changed_regions = []
        
        # Compare children of root nodes to find changes
        old_children = [child for child in old_root.children]
        new_children = [child for child in new_root.children]
        
        # Basic approach: if different number of children or any child differs significantly
        if len(old_children) != len(new_children):
            # Major structural change
            return [{'start_byte': 0, 'end_byte': new_root.end_byte, 'type': 'structural_change'}]
        
        # Compare each child
        for old_child, new_child in zip(old_children, new_children):
            if (old_child.type != new_child.type or 
                old_child.start_byte != new_child.start_byte or
                old_child.end_byte != new_child.end_byte):
                changed_regions.append({
                    'start_byte': new_child.start_byte,
                    'end_byte': new_child.end_byte,
                    'type': 'node_change',
                    'old_type': old_child.type,
                    'new_type': new_child.type
                })
        
        return changed_regions
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get TreeCache performance statistics.
        
        Returns:
            Dictionary with cache hit rate, memory usage, and other metrics
        """
        if not self.tree_cache:
            return {
                'cache_enabled': False,
                'hit_rate': 0.0,
                'total_requests': 0,
                'hits': 0,
                'misses': 0
            }
        
        stats = self.tree_cache.get_stats()
        return {
            'cache_enabled': True,
            'hit_rate': stats.get('hit_rate_percent', 0.0) / 100.0,
            'total_requests': stats.get('total_requests', 0),
            'hits': stats.get('hits', 0),
            'misses': stats.get('misses', 0),
            'evictions': stats.get('evictions', 0),
            'invalidations': stats.get('invalidations', 0),
            'cache_size': stats.get('entries', 0),
            'estimated_memory_mb': stats.get('estimated_memory_mb', 0)
        }
    
    def _parse_python_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse Python file incrementally using TreeCache.
        
        Args:
            file_path: Path to Python file
            source: Optional source code string
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._python_initialized:
            logger.warning("Python parser not initialized, attempting setup")
            self.setup()
            if not self._python_initialized:
                return []
        
        logger.debug(f"Incremental parsing Python file: {file_path}")
        
        try:
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_functions(tree.root_node, source_code))
            chunks.extend(self._extract_classes(tree.root_node, source_code))
            
            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse Python file incrementally {file_path}: {e}")
            return []
    
    def _parse_java_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse Java file incrementally using TreeCache.
        
        Args:
            file_path: Path to Java file
            source: Optional source code string
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._java_initialized:
            logger.warning("Java parser not initialized, attempting setup")
            self.setup()
            if not self._java_initialized:
                return []
        
        logger.debug(f"Incremental parsing Java file: {file_path}")
        
        try:
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []
            
            # Extract package name
            package_name = self._extract_java_package(tree.root_node, source_code)
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_java_classes(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_interfaces(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_enums(tree.root_node, source_code, file_path, package_name))
            chunks.extend(self._extract_java_methods(tree.root_node, source_code, file_path, package_name))
            
            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse Java file incrementally {file_path}: {e}")
            return []
    
    def _parse_markdown_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse Markdown file incrementally using TreeCache.
        
        Args:
            file_path: Path to Markdown file
            source: Optional source code string
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._markdown_initialized:
            logger.warning("Markdown parser not initialized, attempting setup")
            self.setup()
            if not self._markdown_initialized:
                return []
        
        logger.debug(f"Incremental parsing Markdown file: {file_path}")
        
        try:
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []
            
            # Check if tree parsed successfully
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse Markdown file: {file_path}")
                return []

            # Check if tree parsed successfully
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse Python file: {file_path}")
                return []

            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_functions(tree.root_node, source_code))
            chunks.extend(self._extract_classes(tree.root_node, source_code))
            
            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse Markdown file incrementally {file_path}: {e}")
            return []
    
    def _parse_tree_only(self, file_path: Path, source: Optional[str] = None) -> Optional[TreeSitterTree]:
        """Parse file and return only the syntax tree (without chunking).
        
        Args:
            file_path: Path to file to parse
            source: Optional source code string (if None, reads from file)
            
        Returns:
            Parsed syntax tree, or None if parsing failed
        """
        # Determine file type and get appropriate parser
        suffix = file_path.suffix.lower()
        parser = None
        
        if suffix == '.py':
            if not self._python_initialized:
                self.setup()
            parser = self.python_parser
        elif suffix in ['.md', '.markdown']:
            if not self._markdown_initialized:
                self.setup()
            parser = self.markdown_parser
        elif suffix == '.java':
            if not self._java_initialized:
                self.setup()
            parser = self.java_parser
        elif suffix == '.cs':
            if not self._csharp_initialized:
                self.setup()
            parser = self.csharp_parser
        elif suffix == '.ts':
            if not self._typescript_initialized:
                self.setup()
            parser = self.typescript_parser
        elif suffix == '.js':
            if not self._javascript_initialized:
                self.setup()
            parser = self.javascript_parser
        elif suffix == '.tsx':
            if not self._tsx_initialized:
                self.setup()
            parser = self.tsx_parser
        elif suffix == '.jsx':
            if not self._tsx_initialized:
                self.setup()
            parser = self.tsx_parser
        else:
            logger.warning(f"Unsupported file type for tree parsing: {suffix}")
            return None
        
        if parser is None:
            logger.error(f"Parser not available for {suffix}")
            return None
        
        try:
            # Read source code if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
            
            # Parse with tree-sitter
            tree = parser.parse(bytes(source, 'utf8'))
            logger.debug(f"Parsed syntax tree for {file_path}")
            return tree
            
        except Exception as e:
            logger.error(f"Failed to parse tree for {file_path}: {e}")
            return None
            
    def _parse_java_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
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
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Use incremental parsing if cache is enabled
            if self.use_cache:
                tree = self.parse_incremental(file_path, source_code)
            else:
                # Parse with tree-sitter directly
                if self.java_parser is not None:
                    tree = self.java_parser.parse(bytes(source_code, 'utf8'))
                else:
                    logger.error("Java parser is None after initialization check")
                    return []

            # Check if tree parsed successfully
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse Java file: {file_path}")
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
                    "symbol": qualified_name,
                    "start_line": inner_class_node.start_point[0] + 1,
                    "end_line": inner_class_node.end_point[0] + 1,
                    "code": inner_class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": inner_class_text,
                    "start_byte": inner_class_node.start_byte,
                    "end_byte": inner_class_node.end_byte,
                    "parent": outer_class_name
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
                
                # Create display name
                display_name = qualified_name
                
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
                    "display_name": display_name,
                    "content": enum_text,
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
                    "symbol": qualified_name,
                    "start_line": method_node.start_point[0] + 1,
                    "end_line": method_node.end_point[0] + 1,
                    "code": method_text,
                    "chunk_type": ChunkType.METHOD.value,
                    "language": "java",
                    "path": str(file_path),
                    "name": qualified_name,
                    "display_name": display_name,
                    "content": method_text,
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
    
    def _parse_python_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a Python file and extract semantic chunks."""
        if not self._python_initialized:
            logger.warning("Python parser not initialized, attempting setup")
            self.setup()
            if not self._python_initialized:
                return []
        
        logger.debug(f"Parsing Python file: {file_path}")
        
        try:
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Use incremental parsing if cache is enabled
            if self.use_cache:
                tree = self.parse_incremental(file_path, source_code)
            else:
                # Parse with tree-sitter directly
                if self.python_parser is not None:
                    tree = self.python_parser.parse(bytes(source_code, 'utf8'))
                else:
                    return []
            
            # Check if tree parsed successfully
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse Python file: {file_path}")
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
    
    def _parse_markdown_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a Markdown file and extract semantic chunks."""
        if not self._markdown_initialized:
            logger.warning("Markdown parser not initialized, attempting setup")
            self.setup()
            if not self._markdown_initialized:
                return []
        
        logger.debug(f"Parsing Markdown file: {file_path}")
        
        try:
            # Read file content if not provided
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Use incremental parsing if cache is enabled
            if self.use_cache:
                tree = self.parse_incremental(file_path, source_code)
            else:
                # Parse with tree-sitter directly
                if self.markdown_parser is not None:
                    tree = self.markdown_parser.parse(bytes(source_code, 'utf8'))
                else:
                    return []
            
            # Check if tree parsed successfully
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse Markdown file: {file_path}")
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
                    "chunk_type": ChunkType.FUNCTION.value
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
                    "chunk_type": ChunkType.CLASS.value
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
                    "chunk_type": ChunkType.METHOD.value
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
                        
                        # Map header level to ChunkType
                        header_type_map = {
                            1: ChunkType.HEADER_1,
                            2: ChunkType.HEADER_2,
                            3: ChunkType.HEADER_3,
                            4: ChunkType.HEADER_4,
                            5: ChunkType.HEADER_5,
                            6: ChunkType.HEADER_6
                        }
                        
                        chunk = {
                            "symbol": header_text,
                            "start_line": heading_node.start_point[0] + 1,
                            "end_line": heading_node.end_point[0] + 1,
                            "code": self._get_node_text(heading_node, source_code),
                            "chunk_type": header_type_map[level].value,
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
                        "chunk_type": ChunkType.CODE_BLOCK.value,
                        "language_info": language_info
                    }
                    chunks.append(chunk)
                    logger.debug(f"Found code block ({language_info}) at lines {chunk['start_line']}-{chunk['end_line']}")
        
        except Exception as e:
            logger.error(f"Failed to extract code blocks: {e}")
        
        return chunks
    
    def _merge_consecutive_paragraphs(self, paragraphs: List[Dict], source_code: str) -> List[Dict]:
        """Merge consecutive paragraphs that are closely related."""
        if not paragraphs:
            return []
        
        merged = []
        current_group = [paragraphs[0]]
    
        for i in range(1, len(paragraphs)):
            prev_para = current_group[-1]
            curr_para = paragraphs[i]
        
            # Check if paragraphs are consecutive (within 2 lines of each other)
            line_gap = curr_para["start_line"] - prev_para["end_line"]
        
            # Merge if they're very close and both are short
            if (line_gap <= 2 and 
                len(prev_para["text"]) < 100 and 
                len(curr_para["text"]) < 100 and
                len(current_group) < 3):  # Don't merge more than 3 paragraphs
                current_group.append(curr_para)
            else:
                # Finalize current group
                if len(current_group) == 1:
                    merged.append(current_group[0])
                else:
                    # Merge the group into a single paragraph
                    merged_text = "\n\n".join([p["text"] for p in current_group])
                    merged.append({
                        "text": merged_text,
                        "start_line": current_group[0]["start_line"], 
                        "end_line": current_group[-1]["end_line"]
                    })
                current_group = [curr_para]
    
        # Handle the last group
        if len(current_group) == 1:
            merged.append(current_group[0])
        else:
            merged_text = "\n\n".join([p["text"] for p in current_group])
            merged.append({
                "text": merged_text,
                "start_line": current_group[0]["start_line"],
                "end_line": current_group[-1]["end_line"]
            })
        
        return merged

    def _extract_paragraphs(self, tree_node: TreeSitterNode, source_code: str) -> List[Dict[str, Any]]:
        """Extract markdown paragraphs from AST with intelligent filtering."""
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

            # Collect and filter potential paragraphs
            potential_paragraphs = []
            for match in matches:
                pattern_index, captures = match

                if "paragraph" in captures:
                    para_node = captures["paragraph"][0]
                    para_text = self._get_node_text(para_node, source_code).strip()
                    
                    # More stringent filtering for meaningful paragraphs
                    if (len(para_text) < 30 or  # Minimum 30 characters
                        len(para_text.split()) < 5 or  # Minimum 5 words
                        para_node.start_point[0] == para_node.end_point[0]):  # Skip single-line spans
                        continue
                    
                    # Skip if it's mostly punctuation or very short sentences
                    words = para_text.split()
                    if len([w for w in words if len(w) > 2]) < 3:  # Need at least 3 meaningful words
                        continue
                        
                    potential_paragraphs.append({
                        "node": para_node,
                        "text": para_text,
                        "start_line": para_node.start_point[0] + 1,
                        "end_line": para_node.end_point[0] + 1
                    })

            # Merge consecutive paragraphs if they're closely related
            merged_paragraphs = self._merge_consecutive_paragraphs(potential_paragraphs, source_code)
            
            # Create chunks from merged paragraphs
            for para_info in merged_paragraphs:
                words = para_info["text"].split()[:5]
                symbol = " ".join(words) + ("..." if len(words) == 5 else "")
                
                chunk = {
                    "symbol": symbol,
                    "start_line": para_info["start_line"],
                    "end_line": para_info["end_line"],
                    "code": para_info["text"],
                    "chunk_type": ChunkType.PARAGRAPH.value,
                    "language_info": "markdown"
                }
                chunks.append(chunk)
                logger.debug(f"Found paragraph at lines {chunk['start_line']}-{chunk['end_line']}")

        except Exception as e:
            logger.error(f"Failed to extract paragraphs: {e}")

        return chunks
    
    def _parse_csharp_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a C# file and extract semantic chunks.
        
        Args:
            file_path: Path to C# file to parse
            source: Optional source code string
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._csharp_initialized:
            logger.warning("C# parser not initialized, attempting setup")
            self.setup()
            if not self._csharp_initialized:
                logger.error("C# parser initialization failed")
                return []

        logger.debug(f"Parsing C# file: {file_path}")

        try:
            chunks = []
            
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Parse with tree-sitter directly
            if self.csharp_parser is not None:
                tree = self.csharp_parser.parse(bytes(source_code, 'utf8'))
            else:
                logger.error("C# parser is None after initialization check")
                return []
            
            # Extract chunks from each namespace declaration
            namespace_nodes = self._extract_csharp_namespace_nodes(tree.root_node, source_code)
            
            if namespace_nodes:
                # Process each namespace separately
                for namespace_node, namespace_name in namespace_nodes:
                    chunks.extend(self._extract_csharp_classes(namespace_node, source_code, file_path, namespace_name))
                    chunks.extend(self._extract_csharp_interfaces(namespace_node, source_code, file_path, namespace_name))
                    chunks.extend(self._extract_csharp_structs(namespace_node, source_code, file_path, namespace_name))
                    chunks.extend(self._extract_csharp_enums(namespace_node, source_code, file_path, namespace_name))
                    chunks.extend(self._extract_csharp_methods(namespace_node, source_code, file_path, namespace_name))
            else:
                # No namespace declarations - process entire file with empty namespace
                chunks.extend(self._extract_csharp_classes(tree.root_node, source_code, file_path, ""))
                chunks.extend(self._extract_csharp_interfaces(tree.root_node, source_code, file_path, ""))
                chunks.extend(self._extract_csharp_structs(tree.root_node, source_code, file_path, ""))
                chunks.extend(self._extract_csharp_enums(tree.root_node, source_code, file_path, ""))
                chunks.extend(self._extract_csharp_methods(tree.root_node, source_code, file_path, ""))

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse C# file {file_path}: {e}")
            return []
    
    def _parse_csharp_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse C# file incrementally using TreeCache.
        
        Args:
            file_path: Path to C# file
            source: Optional source code string
            
        Returns:
            List of extracted chunks with metadata
        """
        if not self._csharp_initialized:
            logger.warning("C# parser not initialized, attempting setup")
            self.setup()
            if not self._csharp_initialized:
                return []
        
        logger.debug(f"Incremental parsing C# file: {file_path}")
        
        try:
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source
            
            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []
            
            # Extract namespace name
            namespace_name = self._extract_csharp_namespace(tree.root_node, source_code)
            
            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_csharp_classes(tree.root_node, source_code, file_path, namespace_name))
            chunks.extend(self._extract_csharp_interfaces(tree.root_node, source_code, file_path, namespace_name))
            chunks.extend(self._extract_csharp_structs(tree.root_node, source_code, file_path, namespace_name))
            chunks.extend(self._extract_csharp_enums(tree.root_node, source_code, file_path, namespace_name))
            chunks.extend(self._extract_csharp_methods(tree.root_node, source_code, file_path, namespace_name))
            
            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to parse C# file incrementally {file_path}: {e}")
            return []
    
    def _extract_csharp_type_parameters(self, node: TreeSitterNode, source_code: str) -> str:
        """Extract C# generic type parameters from a node.
        
        Args:
            node: AST node to search for type parameters
            source_code: Source code content
            
        Returns:
            String representation of type parameters (e.g., "<T>", "<T, U>") or empty string
        """
        if self.csharp_language is None:
            return ""
            
        try:
            query = self.csharp_language.query("""
                (type_parameter_list) @type_params
            """)
            
            matches = query.matches(node)
            
            for match in matches:
                pattern_index, captures = match
                if "type_params" in captures:
                    type_params_node = captures["type_params"][0]
                    return self._get_node_text(type_params_node, source_code)
            
            return ""
            
        except Exception as e:
            logger.debug(f"Failed to extract C# type parameters: {e}")
            return ""
    
    def _extract_csharp_namespace(self, tree_node: TreeSitterNode, source_code: str) -> str:
        """Extract the namespace name from C# file root node.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            
        Returns:
            Namespace name or empty string if no namespace found
        """
        if self.csharp_language is None:
            return ""
        
        try:
            # Query for namespace declarations - handles both simple and qualified names
            qualified_query = self.csharp_language.query("""
                (namespace_declaration name: (qualified_name) @namespace_qualified)
            """)
            
            matches = qualified_query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                if "namespace_qualified" in captures:
                    namespace_name_node = captures["namespace_qualified"][0]
                    return self._get_node_text(namespace_name_node, source_code).strip()
            
            # Fallback to simple identifier if qualified name not found
            simple_query = self.csharp_language.query("""
                (namespace_declaration name: (identifier) @namespace_name)
            """)
            
            simple_matches = simple_query.matches(tree_node)
            
            for match in simple_matches:
                pattern_index, captures = match
                if "namespace_name" in captures:
                    namespace_name_node = captures["namespace_name"][0]
                    return self._get_node_text(namespace_name_node, source_code).strip()
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting C# namespace: {e}")
            return ""
    
    def _extract_csharp_namespace_nodes(self, tree_node: TreeSitterNode, source_code: str) -> List[Tuple[TreeSitterNode, str]]:
        """Extract all namespace nodes and their names from C# file.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            
        Returns:
            List of tuples (namespace_node, namespace_name)
        """
        if self.csharp_language is None:
            return []
        
        try:
            namespace_info = []
            
            # Query for namespace declarations - handles both simple and qualified names
            qualified_query = self.csharp_language.query("""
                (namespace_declaration name: (qualified_name) @namespace_qualified) @namespace_def
            """)
            
            matches = qualified_query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                if "namespace_def" in captures and "namespace_qualified" in captures:
                    namespace_node = captures["namespace_def"][0]
                    namespace_name_node = captures["namespace_qualified"][0]
                    namespace_name = self._get_node_text(namespace_name_node, source_code).strip()
                    namespace_info.append((namespace_node, namespace_name))
            
            # Fallback to simple identifier if qualified name not found
            simple_query = self.csharp_language.query("""
                (namespace_declaration name: (identifier) @namespace_name) @namespace_def
            """)
            
            simple_matches = simple_query.matches(tree_node)
            
            for match in simple_matches:
                pattern_index, captures = match
                if "namespace_def" in captures and "namespace_name" in captures:
                    namespace_node = captures["namespace_def"][0]
                    namespace_name_node = captures["namespace_name"][0]
                    namespace_name = self._get_node_text(namespace_name_node, source_code).strip()
                    # Only add if not already added by qualified query
                    if not any(ns_name == namespace_name for _, ns_name in namespace_info):
                        namespace_info.append((namespace_node, namespace_name))
            
            return namespace_info
            
        except Exception as e:
            logger.error(f"Failed to extract C# namespace nodes: {e}")
            return []
    
    def _extract_csharp_nested_structs(self, parent_node: TreeSitterNode, source_code: str,
                                     file_path: Path, parent_qualified_name: str) -> List[Dict[str, Any]]:
        """Extract nested C# struct definitions from within a parent class.
        
        Args:
            parent_node: Parent class/struct node to search within
            source_code: Source code content
            file_path: Path to the C# file
            parent_qualified_name: Qualified name of the parent class/struct
            
        Returns:
            List of nested struct chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (struct_declaration name: (identifier) @struct_name) @struct_def
            """)
            
            matches = query.matches(parent_node)
            
            for match in matches:
                pattern_index, captures = match
                struct_node = None
                struct_name = None
                
                # Get struct definition node
                if "struct_def" in captures:
                    struct_node = captures["struct_def"][0]
                    
                # Skip if this is the parent node itself (avoid recursive extraction)
                if struct_node == parent_node:
                    continue
                    
                # Get struct name
                if "struct_name" in captures:
                    struct_name_node = captures["struct_name"][0]
                    struct_name = self._get_node_text(struct_name_node, source_code).strip()
                
                if struct_node and struct_name:
                    start_line = struct_node.start_point[0] + 1
                    end_line = struct_node.end_point[0] + 1
                    
                    # Build qualified nested struct name
                    qualified_name = f"{parent_qualified_name}.{struct_name}"
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(struct_node, source_code),
                        "chunk_type": ChunkType.STRUCT.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(struct_node, source_code),
                        "start_byte": struct_node.start_byte,
                        "end_byte": struct_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# nested struct: {qualified_name} at lines {start_line}-{end_line}")
                    
                    # Extract properties within this nested struct
                    property_chunks = self._extract_csharp_properties(struct_node, source_code, file_path, qualified_name)
                    chunks.extend(property_chunks)
                    
                    # Extract constructors within this nested struct
                    constructor_chunks = self._extract_csharp_constructors(struct_node, source_code, file_path, qualified_name)
                    chunks.extend(constructor_chunks)
                    
        except Exception as e:
            logger.error(f"Failed to extract nested C# structs: {e}")
            return []
            
        return chunks
    
    def _extract_csharp_nested_classes(self, parent_node: TreeSitterNode, source_code: str,
                                     file_path: Path, parent_qualified_name: str) -> List[Dict[str, Any]]:
        """Extract nested C# class definitions from within a parent class.
        
        Args:
            parent_node: Parent class node to search within
            source_code: Source code content
            file_path: Path to the C# file
            parent_qualified_name: Qualified name of the parent class
            
        Returns:
            List of nested class chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (class_declaration name: (identifier) @class_name) @class_def
            """)
            
            matches = query.matches(parent_node)
            
            for match in matches:
                pattern_index, captures = match
                class_node = None
                class_name = None
                
                # Get class definition node
                if "class_def" in captures:
                    class_node = captures["class_def"][0]
                    
                # Skip if this is the parent node itself (avoid recursive extraction)
                if class_node == parent_node:
                    continue
                    
                # Get class name
                if "class_name" in captures:
                    class_name_node = captures["class_name"][0]
                    class_name = self._get_node_text(class_name_node, source_code).strip()
                
                if class_node and class_name:
                    start_line = class_node.start_point[0] + 1
                    end_line = class_node.end_point[0] + 1
                    
                    # Build qualified nested class name
                    qualified_name = f"{parent_qualified_name}.{class_name}"
                    
                    # Check for generic type parameters
                    type_params = self._extract_csharp_type_parameters(class_node, source_code)
                    if type_params:
                        display_name = f"{qualified_name}{type_params}"
                    else:
                        display_name = qualified_name
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(class_node, source_code),
                        "chunk_type": ChunkType.CLASS.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": self._get_node_text(class_node, source_code),
                        "start_byte": class_node.start_byte,
                        "end_byte": class_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# nested class: {qualified_name} at lines {start_line}-{end_line}")
                    
                    # Extract properties within this nested class
                    property_chunks = self._extract_csharp_properties(class_node, source_code, file_path, qualified_name)
                    chunks.extend(property_chunks)
                    
                    # Extract constructors within this nested class
                    constructor_chunks = self._extract_csharp_constructors(class_node, source_code, file_path, qualified_name)
                    chunks.extend(constructor_chunks)
                    
        except Exception as e:
            logger.error(f"Failed to extract nested C# classes: {e}")
            return []
            
        return chunks
    
    def _extract_csharp_classes(self, tree_node: TreeSitterNode, source_code: str, 
                              file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# class definitions from AST.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            file_path: Path to the C# file
            namespace_name: Namespace name for context
            
        Returns:
            List of class chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (class_declaration name: (identifier) @class_name) @class_def
            """)
            
            matches = query.matches(tree_node)
            
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
                    class_name = self._get_node_text(class_name_node, source_code).strip()
                
                if class_node and class_name:
                    start_line = class_node.start_point[0] + 1
                    end_line = class_node.end_point[0] + 1
                    
                    # Build qualified class name
                    qualified_name = f"{namespace_name}.{class_name}" if namespace_name else class_name
                    
                    # Check for generic type parameters
                    type_params = self._extract_csharp_type_parameters(class_node, source_code)
                    if type_params:
                        display_name = f"{qualified_name}{type_params}"
                    else:
                        display_name = qualified_name
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(class_node, source_code),
                        "chunk_type": ChunkType.CLASS.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": self._get_node_text(class_node, source_code),
                        "start_byte": class_node.start_byte,
                        "end_byte": class_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# class: {qualified_name} at lines {start_line}-{end_line}")
                    
                    # Extract properties within this class
                    property_chunks = self._extract_csharp_properties(class_node, source_code, file_path, qualified_name)
                    chunks.extend(property_chunks)
                    
                    # Extract constructors within this class
                    constructor_chunks = self._extract_csharp_constructors(class_node, source_code, file_path, qualified_name)
                    chunks.extend(constructor_chunks)
                    
                    # Extract nested structs within this class
                    nested_struct_chunks = self._extract_csharp_nested_structs(class_node, source_code, file_path, qualified_name)
                    chunks.extend(nested_struct_chunks)
                    
                    # Extract nested classes within this class
                    nested_class_chunks = self._extract_csharp_nested_classes(class_node, source_code, file_path, qualified_name)
                    chunks.extend(nested_class_chunks)
                    
        except Exception as e:
            logger.error(f"Failed to extract C# classes: {e}")
            
        return chunks
    
    def _extract_csharp_interfaces(self, tree_node: TreeSitterNode, source_code: str,
                                 file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# interface definitions from AST.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            file_path: Path to the C# file
            namespace_name: Namespace name for context
            
        Returns:
            List of interface chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("""
                (interface_declaration name: (identifier) @interface_name) @interface_def
            """)
            
            matches = query.matches(tree_node)
            
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
                    interface_name = self._get_node_text(interface_name_node, source_code).strip()
                
                if interface_node and interface_name:
                    start_line = interface_node.start_point[0] + 1
                    end_line = interface_node.end_point[0] + 1
                    
                    # Build qualified interface name
                    qualified_name = f"{namespace_name}.{interface_name}" if namespace_name else interface_name
                    
                    # Check for generic type parameters
                    type_params = self._extract_csharp_type_parameters(interface_node, source_code)
                    if type_params:
                        display_name = f"{qualified_name}{type_params}"
                    else:
                        display_name = qualified_name
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(interface_node, source_code),
                        "chunk_type": ChunkType.INTERFACE.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": display_name,
                        "content": self._get_node_text(interface_node, source_code),
                        "start_byte": interface_node.start_byte,
                        "end_byte": interface_node.end_byte,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# interface: {qualified_name} at lines {start_line}-{end_line}")
                    
        except Exception as e:
            logger.error(f"Failed to extract C# interfaces: {e}")
            
        return chunks
    
    def _extract_csharp_methods(self, tree_node: TreeSitterNode, source_code: str,
                              file_path: Path, namespace_name: str) -> List[Dict[str, Any]]:
        """Extract C# method definitions from AST.
        
        Args:
            tree_node: Root node of the C# AST
            source_code: Source code content
            file_path: Path to the C# file
            namespace_name: Namespace name for context
            
        Returns:
            List of method chunks with metadata
        """
        chunks = []
        
        if self.csharp_language is None:
            return []
            
        try:
            # Use simpler query approach
            query = self.csharp_language.query("(method_declaration) @method")
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                method_node = None
                
                # Get method definition node
                if "method" in captures:
                    method_node = captures["method"][0]  # Take first match
                
                if method_node:
                    # Extract method name from children
                    method_name = None
                    for child in method_node.children:
                        if child.type == "identifier":
                            method_name = self._get_node_text(child, source_code).strip()
                            break
                    
                    if not method_name:
                        continue
                        
                    start_line = method_node.start_point[0] + 1
                    end_line = method_node.end_point[0] + 1
                    
                    # Try to find containing class/interface/struct for context
                    parent = method_node.parent
                    parent_context = ""
                    while parent:
                        if parent.type in ["class_declaration", "interface_declaration", "struct_declaration"]:
                            # Find parent name from its children
                            for child in parent.children:
                                if child.type == "identifier":
                                    parent_context = self._get_node_text(child, source_code).strip()
                                    break
                            break
                        parent = parent.parent
                
                    # Extract method parameters for signature (simplified)
                    params = []
                    try:
                        param_query = self.csharp_language.query("(parameter) @param")
                        param_matches = param_query.matches(method_node)
                        
                        for param_match in param_matches:
                            param_pattern_index, param_captures = param_match
                            if "param" in param_captures:
                                param_node = param_captures["param"][0]
                                # Extract type from parameter node
                                for child in param_node.children:
                                    if child.type in ["predefined_type", "identifier", "generic_name"]:
                                        param_type = self._get_node_text(child, source_code).strip()
                                        params.append(param_type)
                                        break
                    except:
                        pass  # Continue without parameters if extraction fails
                    
                    param_str = ", ".join(params) if params else ""
                
                    # Build qualified method name with parameters
                    if parent_context:
                        qualified_parent = f"{namespace_name}.{parent_context}" if namespace_name else parent_context
                        qualified_name = f"{qualified_parent}.{method_name}({param_str})"
                    else:
                        qualified_name = f"{namespace_name}.{method_name}({param_str})" if namespace_name else f"{method_name}({param_str})"
                    
                    chunk = {
                        "symbol": qualified_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "code": self._get_node_text(method_node, source_code),
                        "chunk_type": ChunkType.METHOD.value,
                        "language": "csharp",
                        "path": str(file_path),
                        "name": qualified_name,
                        "display_name": qualified_name,
                        "content": self._get_node_text(method_node, source_code),
                        "start_byte": method_node.start_byte,
                        "end_byte": method_node.end_byte,
                        "parent": parent_context,
                        "parameters": params,
                    }
                    
                    chunks.append(chunk)
                    logger.debug(f"Found C# method: {qualified_name} at lines {start_line}-{end_line}")
                    
        except Exception as e:
            logger.error(f"Failed to extract C# methods: {e}")
            
        return chunks
    
    def _extract_csharp_method_parameters(self, method_node: TreeSitterNode, source_code: str) -> List[str]:
        """Extract parameter types from a C# method.
        
        Args:
            method_node: Method AST node
            source_code: Source code content
            
        Returns:
            List of parameter type strings
        """
        if self.csharp_language is None:
            return []
            
        try:
            query = self.csharp_language.query("(parameter) @param")
            
            matches = query.matches(method_node)
            param_types = []
            
            for match in matches:
                pattern_index, captures = match
                if "param" in captures:
                    param_node = captures["param"][0]
                    # Extract type from parameter node
                    for child in param_node.children:
                        if child.type in ["predefined_type", "identifier", "generic_name"]:
                            param_type = self._get_node_text(child, source_code).strip()
                            param_types.append(param_type)
                            break
                    
            return param_types
            
        except Exception as e:
            logger.error(f"Failed to extract method parameters: {e}")
            return []

    # ========================================
    # TypeScript/JavaScript Parser Methods
    # ========================================

    def _parse_typescript_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a TypeScript file and extract semantic chunks.

        Args:
            file_path: Path to TypeScript file to parse
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._typescript_initialized:
            logger.warning("TypeScript parser not initialized, attempting setup")
            self.setup()
            if not self._typescript_initialized:
                logger.error("TypeScript parser initialization failed")
                return []

        logger.debug(f"Parsing TypeScript file: {file_path}")

        try:
            chunks = []

            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Parse with tree-sitter
            if self.typescript_parser is not None:
                tree = self.typescript_parser.parse(bytes(source_code, 'utf8'))
            else:
                logger.error("TypeScript parser is None after initialization check")
                return []

            # Extract TypeScript semantic units
            chunks.extend(self._extract_typescript_functions(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_classes(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_interfaces(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_enums(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_types(tree.root_node, source_code, file_path))

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse TypeScript file {file_path}: {e}")
            return []

    def _parse_javascript_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a TSX file and extract semantic chunks.

        Args:
            file_path: Path to TSX file to parse
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._tsx_initialized:
            logger.warning("TSX parser not initialized, attempting setup")
            self.setup()
            if not self._tsx_initialized:
                logger.error("TSX parser initialization failed")
                return []

        logger.debug(f"Parsing TSX file: {file_path}")

        try:
            chunks = []

            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Parse with tree-sitter
            if self.tsx_parser is not None:
                tree = self.tsx_parser.parse(bytes(source_code, 'utf8'))
            else:
                logger.error("TSX parser is None after initialization check")
                return []

            # Extract TSX semantic units (same as TypeScript with React components)
            chunks.extend(self._extract_typescript_functions(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_classes(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_interfaces(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_enums(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_types(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_tsx_components(tree.root_node, source_code, file_path))

            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse TSX file {file_path}: {e}")
            return []

    def _parse_jsx_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a JSX file and extract semantic chunks.

        Args:
            file_path: Path to JSX file to parse
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        # JSX files use the TSX parser (same syntax)
        return self._parse_tsx_file(file_path, source)

    # Incremental parsing methods for TypeScript/JavaScript

    def _parse_typescript_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse TypeScript file incrementally using TreeCache.

        Args:
            file_path: Path to TypeScript file
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._typescript_initialized:
            logger.warning("TypeScript parser not initialized, attempting setup")
            self.setup()
            if not self._typescript_initialized:
                return []

        logger.debug(f"Incremental parsing TypeScript file: {file_path}")

        try:
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []

            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_typescript_functions(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_classes(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_interfaces(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_enums(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_types(tree.root_node, source_code, file_path))

            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse TypeScript file incrementally {file_path}: {e}")
            return []

    def _parse_javascript_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse JavaScript file incrementally using TreeCache.

        Args:
            file_path: Path to JavaScript file
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._javascript_initialized:
            logger.warning("JavaScript parser not initialized, attempting setup")
            self.setup()
            if not self._javascript_initialized:
                return []

        logger.debug(f"Incremental parsing JavaScript file: {file_path}")

        try:
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []

            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_javascript_functions(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_javascript_classes(tree.root_node, source_code, file_path))

            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse JavaScript file incrementally {file_path}: {e}")
            return []

    def _parse_tsx_file(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse a TSX file and extract semantic chunks.

        Args:
            file_path: Path to TSX file to parse
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._tsx_initialized:
            logger.warning("TSX parser not initialized, attempting setup")
            self.setup()
            if not self._tsx_initialized:
                return []

        logger.debug(f"Parsing TSX file: {file_path}")

        try:
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Parse with tree-sitter
            if self.typescript_parser is not None:
                tree = self.typescript_parser.parse(bytes(source_code, 'utf8'))
            else:
                logger.error("TypeScript parser is None after initialization check")
                return []
            
            if tree is None or tree.root_node is None:
                logger.warning(f"Failed to parse TSX file: {file_path}")
                return []

            # Extract chunks using TypeScript logic (TSX is TypeScript + JSX)
            chunks = self._extract_typescript_classes(tree.root_node, source_code, file_path)
            chunks.extend(self._extract_typescript_interfaces(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_functions(tree.root_node, source_code, file_path))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Error parsing TSX file {file_path}: {e}")
            return []

    def _parse_tsx_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse TSX file incrementally using TreeCache.

        Args:
            file_path: Path to TSX file
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        if not self._tsx_initialized:
            logger.warning("TSX parser not initialized, attempting setup")
            self.setup()
            if not self._tsx_initialized:
                return []

        logger.debug(f"Incremental parsing TSX file: {file_path}")

        try:
            # Get source code
            if source is None:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            else:
                source_code = source

            # Get cached tree or parse new one
            tree = self.parse_incremental(file_path, source_code)
            if tree is None:
                logger.error(f"Failed to parse syntax tree for {file_path}")
                return []

            # Extract semantic units
            chunks = []
            chunks.extend(self._extract_typescript_functions(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_classes(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_interfaces(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_enums(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_typescript_types(tree.root_node, source_code, file_path))
            chunks.extend(self._extract_tsx_components(tree.root_node, source_code, file_path))

            logger.debug(f"Incremental parsing extracted {len(chunks)} chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse TSX file incrementally {file_path}: {e}")
            return []

    def _parse_jsx_file_incremental(self, file_path: Path, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse JSX file incrementally using TreeCache.

        Args:
            file_path: Path to JSX file
            source: Optional source code string

        Returns:
            List of extracted chunks with metadata
        """
        # JSX files use the TSX parser (same syntax)
        return self._parse_tsx_file_incremental(file_path, source)

    # TypeScript semantic extraction methods

    def _extract_typescript_functions(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript function declarations from AST.

        Args:
            tree_node: Root node of the TypeScript AST
            source_code: Source code content
            file_path: Path to the TypeScript file

        Returns:
            List of function chunks with metadata
        """
        chunks = []

        if self.typescript_language is None:
            return []

        try:
            # Query for various function types in TypeScript
            query = self.typescript_language.query("""
                [
                    (function_declaration name: (identifier) @func_name) @func_def
                    (arrow_function) @arrow_func
                    (function_expression) @func_expr
                    (method_definition name: (property_identifier) @method_name) @method_def
                ]
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                func_node = None
                func_name = "anonymous"

                # Get function definition node and name
                for capture_name, nodes in captures.items():
                    if capture_name in ["func_def", "arrow_func", "func_expr", "method_def"]:
                        func_node = nodes[0]
                    elif capture_name in ["func_name", "method_name"]:
                        func_name = self._get_node_text(nodes[0], source_code).strip()

                if func_node is None:
                    continue

                # Get function text
                func_text = self._get_node_text(func_node, source_code)
                start_line = func_node.start_point[0] + 1
                end_line = func_node.end_point[0] + 1

                chunks.append({
                    "symbol": func_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": func_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language_info": "typescript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TypeScript functions: {e}")
            return []

    def _extract_typescript_classes(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript class declarations from AST.

        Args:
            tree_node: Root node of the TypeScript AST
            source_code: Source code content
            file_path: Path to the TypeScript file

        Returns:
            List of class chunks with metadata
        """
        chunks = []

        if self.typescript_language is None:
            return []

        try:
            query = self.typescript_language.query("""
                (class_declaration name: (type_identifier) @class_name) @class_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                class_node = None
                class_name = "UnnamedClass"

                if "class_def" in captures:
                    class_node = captures["class_def"][0]
                if "class_name" in captures:
                    class_name = self._get_node_text(captures["class_name"][0], source_code).strip()

                if class_node is None:
                    continue

                # Get class text
                class_text = self._get_node_text(class_node, source_code)
                start_line = class_node.start_point[0] + 1
                end_line = class_node.end_point[0] + 1

                chunks.append({
                    "symbol": class_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language_info": "typescript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TypeScript classes: {e}")
            return []

    def _extract_typescript_interfaces(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript interface declarations from AST.

        Args:
            tree_node: Root node of the TypeScript AST
            source_code: Source code content
            file_path: Path to the TypeScript file

        Returns:
            List of interface chunks with metadata
        """
        chunks = []

        if self.typescript_language is None:
            return []

        try:
            query = self.typescript_language.query("""
                (interface_declaration name: (type_identifier) @interface_name) @interface_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                interface_node = None
                interface_name = "UnnamedInterface"

                if "interface_def" in captures:
                    interface_node = captures["interface_def"][0]
                if "interface_name" in captures:
                    interface_name = self._get_node_text(captures["interface_name"][0], source_code).strip()

                if interface_node is None:
                    continue

                # Get interface text
                interface_text = self._get_node_text(interface_node, source_code)
                start_line = interface_node.start_point[0] + 1
                end_line = interface_node.end_point[0] + 1

                chunks.append({
                    "symbol": interface_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": interface_text,
                    "chunk_type": ChunkType.INTERFACE.value,
                    "language_info": "typescript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TypeScript interfaces: {e}")
            return []

    def _extract_typescript_enums(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript enum declarations from AST.

        Args:
            tree_node: Root node of the TypeScript AST
            source_code: Source code content
            file_path: Path to the TypeScript file

        Returns:
            List of enum chunks with metadata
        """
        chunks = []

        if self.typescript_language is None:
            return []

        try:
            query = self.typescript_language.query("""
                (enum_declaration name: (identifier) @enum_name) @enum_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                enum_node = None
                enum_name = "UnnamedEnum"

                if "enum_def" in captures:
                    enum_node = captures["enum_def"][0]
                if "enum_name" in captures:
                    enum_name = self._get_node_text(captures["enum_name"][0], source_code).strip()

                if enum_node is None:
                    continue

                # Get enum text
                enum_text = self._get_node_text(enum_node, source_code)
                start_line = enum_node.start_point[0] + 1
                end_line = enum_node.end_point[0] + 1

                chunks.append({
                    "symbol": enum_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": enum_text,
                    "chunk_type": ChunkType.ENUM.value,
                    "language_info": "typescript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TypeScript enums: {e}")
            return []

    def _extract_typescript_types(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract TypeScript type alias declarations from AST.

        Args:
            tree_node: Root node of the TypeScript AST
            source_code: Source code content
            file_path: Path to the TypeScript file

        Returns:
            List of type alias chunks with metadata
        """
        chunks = []

        if self.typescript_language is None:
            return []

        try:
            query = self.typescript_language.query("""
                (type_alias_declaration name: (type_identifier) @type_name) @type_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                type_node = None
                type_name = "UnnamedType"

                if "type_def" in captures:
                    type_node = captures["type_def"][0]
                if "type_name" in captures:
                    type_name = self._get_node_text(captures["type_name"][0], source_code).strip()

                if type_node is None:
                    continue

                # Get type text
                type_text = self._get_node_text(type_node, source_code)
                start_line = type_node.start_point[0] + 1
                end_line = type_node.end_point[0] + 1

                chunks.append({
                    "symbol": type_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": type_text,
                    "chunk_type": ChunkType.TYPE_ALIAS.value,
                    "language_info": "typescript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TypeScript types: {e}")
            return []

    def _extract_tsx_components(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract React component declarations from TSX AST.

        Args:
            tree_node: Root node of the TSX AST
            source_code: Source code content
            file_path: Path to the TSX file

        Returns:
            List of component chunks with metadata
        """
        chunks = []

        if self.tsx_language is None:
            return []

        try:
            # Query for React functional components (functions that return JSX)
            query = self.tsx_language.query("""
                (function_declaration 
                    name: (identifier) @component_name
                    body: (statement_block 
                        (return_statement 
                            (jsx_element)
                        )
                    )
                ) @component_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                component_node = None
                component_name = "UnnamedComponent"

                if "component_def" in captures:
                    component_node = captures["component_def"][0]
                if "component_name" in captures:
                    component_name = self._get_node_text(captures["component_name"][0], source_code).strip()

                if component_node is None:
                    continue

                # Get component text
                component_text = self._get_node_text(component_node, source_code)
                start_line = component_node.start_point[0] + 1
                end_line = component_node.end_point[0] + 1

                chunks.append({
                    "symbol": f"component {component_name}",
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": component_text,
                    "chunk_type": "component",
                    "language_info": "tsx"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract TSX components: {e}")
            return []

    # JavaScript semantic extraction methods

    def _extract_javascript_functions(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract JavaScript function declarations from AST.

        Args:
            tree_node: Root node of the JavaScript AST
            source_code: Source code content
            file_path: Path to the JavaScript file

        Returns:
            List of function chunks with metadata
        """
        chunks = []

        if self.javascript_language is None:
            return []

        try:
            # Query for various function types in JavaScript
            query = self.javascript_language.query("""
                [
                    (function_declaration name: (identifier) @func_name) @func_def
                    (arrow_function) @arrow_func
                    (function_expression) @func_expr
                    (method_definition name: (property_identifier) @method_name) @method_def
                ]
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                func_node = None
                func_name = "anonymous"

                # Get function definition node and name
                for capture_name, nodes in captures.items():
                    if capture_name in ["func_def", "arrow_func", "func_expr", "method_def"]:
                        func_node = nodes[0]
                    elif capture_name in ["func_name", "method_name"]:
                        func_name = self._get_node_text(nodes[0], source_code).strip()

                if func_node is None:
                    continue

                # Get function text
                func_text = self._get_node_text(func_node, source_code)
                start_line = func_node.start_point[0] + 1
                end_line = func_node.end_point[0] + 1

                chunks.append({
                    "symbol": func_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": func_text,
                    "chunk_type": ChunkType.FUNCTION.value,
                    "language_info": "javascript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract JavaScript functions from JSX: {e}")
            return []

    def _extract_javascript_classes(self, tree_node: TreeSitterNode, source_code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract JavaScript class declarations from AST.

        Args:
            tree_node: Root node of the JavaScript AST
            source_code: Source code content
            file_path: Path to the JavaScript file

        Returns:
            List of class chunks with metadata
        """
        chunks = []

        if self.javascript_language is None:
            return []

        try:
            query = self.javascript_language.query("""
                (class_declaration name: (identifier) @class_name) @class_def
            """)

            matches = query.matches(tree_node)

            for match in matches:
                pattern_index, captures = match
                class_node = None
                class_name = "UnnamedClass"

                if "class_def" in captures:
                    class_node = captures["class_def"][0]
                if "class_name" in captures:
                    class_name = self._get_node_text(captures["class_name"][0], source_code).strip()

                if class_node is None:
                    continue

                # Get class text
                class_text = self._get_node_text(class_node, source_code)
                start_line = class_node.start_point[0] + 1
                end_line = class_node.end_point[0] + 1

                chunks.append({
                    "symbol": class_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": class_text,
                    "chunk_type": ChunkType.CLASS.value,
                    "language_info": "javascript"
                })

            return chunks

        except Exception as e:
            logger.error(f"Failed to extract JavaScript classes: {e}")
            return []