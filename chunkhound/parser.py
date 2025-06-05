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

from loguru import logger


class CodeParser:
    """Tree-sitter based code parser for extracting semantic units."""
    
    def __init__(self):
        """Initialize the code parser."""
        self.python_language: Optional[TreeSitterLanguage] = None
        self.python_parser: Optional[TreeSitterParser] = None
        self.markdown_language: Optional[TreeSitterLanguage] = None
        self.markdown_parser: Optional[TreeSitterParser] = None
        self._python_initialized = False
        self._markdown_initialized = False
        
    def setup(self) -> None:
        """Set up tree-sitter parsers for Python and Markdown."""
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
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return []
    
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
        """Extract text content from a tree-sitter node."""
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