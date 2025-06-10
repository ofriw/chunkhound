"""Markdown language parser provider implementation for ChunkHound - concrete parser using tree-sitter."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import time

from loguru import logger

from core.types import ChunkType, Language as CoreLanguage
from interfaces.language_parser import ParseConfig, ParseResult

try:
    import tree_sitter_markdown as tsmarkdown
    from tree_sitter import Language as TSLanguage, Parser as TSParser, Node as TSNode
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    tsmarkdown = None
    TSLanguage = None
    TSParser = None
    TSNode = None


class MarkdownParser:
    """Markdown language parser using tree-sitter."""
    
    def __init__(self, config: Optional[ParseConfig] = None):
        """Initialize Markdown parser.
        
        Args:
            config: Optional parse configuration
        """
        self._language = None
        self._parser = None
        self._initialized = False
        
        # Default configuration
        self._config = config or ParseConfig(
            language=CoreLanguage.MARKDOWN,
            chunk_types={
                ChunkType.HEADER_1,
                ChunkType.HEADER_2,
                ChunkType.HEADER_3,
                ChunkType.HEADER_4,
                ChunkType.HEADER_5,
                ChunkType.HEADER_6,
                ChunkType.CODE_BLOCK,
                ChunkType.PARAGRAPH
            },
            max_chunk_size=8000,
            min_chunk_size=100,
            include_imports=False,
            include_comments=False,
            include_docstrings=False,
            max_depth=10,
            use_cache=True
        )
        
        # Initialize if available
        if MARKDOWN_AVAILABLE:
            self._initialize()
    
    def _initialize(self) -> bool:
        """Initialize the Markdown parser.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not MARKDOWN_AVAILABLE:
            logger.error("Markdown tree-sitter support not available")
            return False
        
        try:
            if tsmarkdown and TSLanguage and TSParser:
                self._language = TSLanguage(tsmarkdown.language())
                self._parser = TSParser(self._language)
                self._initialized = True
                logger.debug("Markdown parser initialized successfully")
                return True
            else:
                logger.error("Markdown parser dependencies not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize Markdown parser: {e}")
            return False
    
    @property
    def language(self) -> CoreLanguage:
        """Programming language this parser handles."""
        return CoreLanguage.MARKDOWN
    
    @property
    def supported_chunk_types(self) -> Set[ChunkType]:
        """Chunk types this parser can extract."""
        return self._config.chunk_types
    
    @property
    def is_available(self) -> bool:
        """Whether the parser is available and ready to use."""
        return MARKDOWN_AVAILABLE and self._initialized
    
    def parse_file(self, file_path: Path, source: Optional[str] = None) -> ParseResult:
        """Parse a Markdown file and extract semantic chunks.
        
        Args:
            file_path: Path to Markdown file
            source: Optional source code string
            
        Returns:
            ParseResult with extracted chunks and metadata
        """
        start_time = time.time()
        chunks = []
        errors = []
        warnings = []
        
        if not self.is_available:
            errors.append("Markdown parser not available")
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
                errors.append("Markdown parser not initialized")
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
            if any(ht in self._config.chunk_types for ht in [ChunkType.HEADER_1, ChunkType.HEADER_2, ChunkType.HEADER_3, ChunkType.HEADER_4, ChunkType.HEADER_5, ChunkType.HEADER_6]):
                chunks.extend(self._extract_headers(tree.root_node, source, file_path))
            
            if ChunkType.CODE_BLOCK in self._config.chunk_types:
                chunks.extend(self._extract_code_blocks(tree.root_node, source, file_path))
            
            if ChunkType.PARAGRAPH in self._config.chunk_types:
                chunks.extend(self._extract_paragraphs(tree.root_node, source, file_path))
            
            logger.debug(f"Extracted {len(chunks)} chunks from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to parse Markdown file {file_path}: {e}"
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
    
    def _extract_headers(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract Markdown headers from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (atx_heading) @header
                (setext_heading) @header
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "header" not in captures:
                    continue
                
                header_node = captures["header"][0]
                header_text = self._get_node_text(header_node, source).strip()
                
                # Extract header level and content
                header_level = 1
                header_content = header_text
                
                if header_text.startswith('#'):
                    # ATX header (# ## ###)
                    header_level = len(header_text) - len(header_text.lstrip('#'))
                    header_content = header_text.lstrip('#').strip()
                else:
                    # Setext header (underlined with = or -)
                    lines = header_text.split('\n')
                    if len(lines) >= 2:
                        header_content = lines[0].strip()
                        underline = lines[1].strip()
                        if '=' in underline:
                            header_level = 1
                        elif '-' in underline:
                            header_level = 2
                
                # Map header level to ChunkType
                header_type_map = {
                    1: ChunkType.HEADER_1,
                    2: ChunkType.HEADER_2,
                    3: ChunkType.HEADER_3,
                    4: ChunkType.HEADER_4,
                    5: ChunkType.HEADER_5,
                    6: ChunkType.HEADER_6
                }
                chunk_type = header_type_map.get(header_level, ChunkType.HEADER_1)
                
                # Create a simple symbol from the header content
                symbol = header_content.lower().replace(' ', '_').replace('-', '_')
                # Remove non-alphanumeric characters except underscores
                symbol = ''.join(c for c in symbol if c.isalnum() or c == '_')
                
                # Fallback for empty symbols (e.g., headers with only special chars/emojis)
                if not symbol:
                    symbol = f"header_{header_node.start_point[0] + 1}"
                
                chunk = {
                    "symbol": symbol,
                    "start_line": header_node.start_point[0] + 1,
                    "end_line": header_node.end_point[0] + 1,
                    "code": header_text,
                    "chunk_type": chunk_type.value,
                    "language": "markdown",
                    "path": str(file_path),
                    "name": header_content,
                    "display_name": header_content,
                    "content": header_text,
                    "start_byte": header_node.start_byte,
                    "end_byte": header_node.end_byte,
                    "header_level": header_level,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Markdown headers: {e}")
        
        return chunks
    
    def _extract_code_blocks(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract Markdown code blocks from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (fenced_code_block) @code_block
                (indented_code_block) @code_block
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "code_block" not in captures:
                    continue
                
                code_block_node = captures["code_block"][0]
                code_block_text = self._get_node_text(code_block_node, source)
                
                # Extract language if specified (for fenced code blocks)
                language_info = ""
                code_content = code_block_text
                
                if code_block_text.startswith('```'):
                    # Fenced code block
                    lines = code_block_text.split('\n')
                    if len(lines) > 0:
                        first_line = lines[0][3:].strip()  # Remove ```
                        if first_line:
                            language_info = first_line
                        # Get content without fences
                        if len(lines) > 2:
                            code_content = '\n'.join(lines[1:-1])
                        else:
                            code_content = ""
                
                # Create symbol for code block
                symbol = f"code_block_{code_block_node.start_point[0] + 1}"
                if language_info:
                    symbol += f"_{language_info}"
                
                display_name = f"Code Block"
                if language_info:
                    display_name += f" ({language_info})"
                
                chunk = {
                    "symbol": symbol,
                    "start_line": code_block_node.start_point[0] + 1,
                    "end_line": code_block_node.end_point[0] + 1,
                    "code": code_block_text,
                    "chunk_type": ChunkType.CODE_BLOCK.value,
                    "language": "markdown",
                    "path": str(file_path),
                    "name": symbol,
                    "display_name": display_name,
                    "content": code_block_text,
                    "start_byte": code_block_node.start_byte,
                    "end_byte": code_block_node.end_byte,
                    "code_language": language_info if language_info else "text",
                    "code_content": code_content,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Markdown code blocks: {e}")
        
        return chunks
    
    def _extract_paragraphs(self, tree_node: TSNode, source: str, file_path: Path) -> List[Dict[str, Any]]:
        """Extract Markdown paragraphs from AST."""
        chunks = []
        
        try:
            if self._language is None:
                return chunks
                
            query = self._language.query("""
                (paragraph) @paragraph
            """)
            
            matches = query.matches(tree_node)
            
            for match in matches:
                pattern_index, captures = match
                
                if "paragraph" not in captures:
                    continue
                
                paragraph_node = captures["paragraph"][0]
                paragraph_text = self._get_node_text(paragraph_node, source).strip()
                
                # Skip very short paragraphs
                if len(paragraph_text) < self._config.min_chunk_size:
                    continue
                
                # Create symbol from first few words
                words = paragraph_text.split()[:5]
                symbol = '_'.join(word.lower() for word in words if word.isalnum())
                if not symbol:
                    symbol = f"paragraph_{paragraph_node.start_point[0] + 1}"
                
                # Truncate display name if too long
                display_name = paragraph_text[:100]
                if len(paragraph_text) > 100:
                    display_name += "..."
                
                chunk = {
                    "symbol": symbol,
                    "start_line": paragraph_node.start_point[0] + 1,
                    "end_line": paragraph_node.end_point[0] + 1,
                    "code": paragraph_text,
                    "chunk_type": ChunkType.PARAGRAPH.value,
                    "language": "markdown",
                    "path": str(file_path),
                    "name": symbol,
                    "display_name": display_name,
                    "content": paragraph_text,
                    "start_byte": paragraph_node.start_byte,
                    "end_byte": paragraph_node.end_byte,
                }
                
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Failed to extract Markdown paragraphs: {e}")
        
        return chunks