"""Tests for the base tree-sitter parser functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from chunkhound.core.types.common import Language, ChunkType
from chunkhound.interfaces.language_parser import ParseConfig
from chunkhound.providers.parsing.base_parser import TreeSitterParserBase


class MockParser(TreeSitterParserBase):
    """Mock parser for testing base functionality."""
    
    def __init__(self, config=None):
        super().__init__(Language.PYTHON, config)
    
    def _extract_chunks(self, tree_node, source, file_path):
        """Mock implementation that returns a single chunk."""
        if hasattr(tree_node, 'start_point') and hasattr(tree_node, 'end_point'):
            return [self._create_chunk(
                tree_node, source, file_path,
                ChunkType.FUNCTION, "mock_function", "mock_function()",
                test_field="test_value"
            )]
        return []


@pytest.fixture
def mock_parser():
    """Create a mock parser instance."""
    return MockParser()


def test_base_parser_initialization():
    """Test base parser initialization."""
    config = ParseConfig(
        language=Language.PYTHON,
        chunk_types={ChunkType.FUNCTION, ChunkType.CLASS},
        max_chunk_size=5000
    )
    
    parser = MockParser(config)
    
    assert parser.language == Language.PYTHON
    assert parser._config.max_chunk_size == 5000
    assert ChunkType.FUNCTION in parser.supported_chunk_types
    assert ChunkType.CLASS in parser.supported_chunk_types


def test_default_config():
    """Test default configuration generation."""
    parser = MockParser()
    
    # Should have default configuration
    assert parser._config is not None
    assert parser._config.language == Language.PYTHON
    assert ChunkType.FUNCTION in parser._config.chunk_types
    assert ChunkType.CLASS in parser._config.chunk_types


def test_create_chunk():
    """Test chunk creation helper method."""
    parser = MockParser()
    
    # Mock AST node
    mock_node = MagicMock()
    mock_node.start_point = [10, 5]  # line 11, column 6 (0-indexed)
    mock_node.end_point = [15, 10]   # line 16, column 11 (0-indexed)
    mock_node.start_byte = 100
    mock_node.end_byte = 200
    
    source = "x" * 100 + "def test_function():\n    pass\n" + "x" * 100
    file_path = Path("/test/file.py")
    
    chunk = parser._create_chunk(
        mock_node, source, file_path,
        ChunkType.FUNCTION, "test_function", "test_function()",
        parameters=["arg1", "arg2"],
        return_type="str"
    )
    
    # Verify chunk structure
    assert chunk["symbol"] == "test_function"
    assert chunk["name"] == "test_function"
    assert chunk["display_name"] == "test_function()"
    assert chunk["start_line"] == 11  # 1-indexed
    assert chunk["end_line"] == 16    # 1-indexed
    assert chunk["start_byte"] == 100
    assert chunk["end_byte"] == 200
    assert chunk["chunk_type"] == ChunkType.FUNCTION.value
    assert chunk["language"] == "python"
    assert chunk["path"] == str(file_path)
    assert chunk["parameters"] == ["arg1", "arg2"]
    assert chunk["return_type"] == "str"
    
    # Code should be extracted from source
    expected_code = source[100:200]
    assert chunk["code"] == expected_code
    assert chunk["content"] == expected_code


def test_create_chunk_with_parent():
    """Test chunk creation with parent information."""
    parser = MockParser()
    
    mock_node = MagicMock()
    mock_node.start_point = [5, 0]
    mock_node.end_point = [10, 0]
    mock_node.start_byte = 50
    mock_node.end_byte = 150
    
    source = "x" * 50 + "def method():\n    pass\n" + "x" * 100
    file_path = Path("/test/file.py")
    
    chunk = parser._create_chunk(
        mock_node, source, file_path,
        ChunkType.METHOD, "ClassName.method", "ClassName.method()",
        parent="ClassName"
    )
    
    assert chunk["parent"] == "ClassName"
    assert chunk["symbol"] == "ClassName.method"


def test_get_node_text():
    """Test node text extraction."""
    parser = MockParser()
    
    mock_node = MagicMock()
    mock_node.start_byte = 10
    mock_node.end_byte = 25
    
    source = "some code def function(): pass more code"
    
    text = parser._get_node_text(mock_node, source)
    assert text == "def function():"


def test_parse_file_not_available():
    """Test parse_file when parser is not available."""
    parser = MockParser()
    parser._initialized = False  # Simulate unavailable parser
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test(): pass")
        f.flush()
        
        try:
            result = parser.parse_file(Path(f.name))
            
            assert result.total_chunks == 0
            assert len(result.errors) > 0
            assert "parser not available" in result.errors[0].lower()
            
        finally:
            Path(f.name).unlink()


def test_parse_file_with_source():
    """Test parse_file with provided source code."""
    parser = MockParser()
    
    # Create mock tree-sitter components if available
    if parser.is_available:
        source = "def test(): pass"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("different content")  # File content should be ignored
            f.flush()
            
            try:
                result = parser.parse_file(Path(f.name), source=source)
                
                # Should use provided source, not file content
                # If parser is working, it should process the provided source
                assert result is not None
                
            finally:
                Path(f.name).unlink()


def test_tree_sitter_language_name():
    """Test tree-sitter language name mapping."""
    parser = MockParser()
    
    # Should default to language enum value
    assert parser._get_tree_sitter_language_name() == "python"


def test_extract_chunks_not_implemented():
    """Test that base class _extract_chunks must be implemented by subclasses."""
    
    # Direct instantiation should work with our mock
    parser = MockParser()
    
    # But a pure base class should raise NotImplementedError
    class IncompleteParser(TreeSitterParserBase):
        def __init__(self):
            super().__init__(Language.PYTHON)
        # Missing _extract_chunks implementation
    
    incomplete_parser = IncompleteParser()
    
    with pytest.raises(NotImplementedError):
        incomplete_parser._extract_chunks(None, "", Path("/test"))


def test_language_property():
    """Test language property returns correct language."""
    parser = MockParser()
    assert parser.language == Language.PYTHON


def test_supported_chunk_types():
    """Test supported chunk types property."""
    config = ParseConfig(
        language=Language.PYTHON,
        chunk_types={ChunkType.FUNCTION, ChunkType.CLASS, ChunkType.METHOD}
    )
    
    parser = MockParser(config)
    supported = parser.supported_chunk_types
    
    assert ChunkType.FUNCTION in supported
    assert ChunkType.CLASS in supported  
    assert ChunkType.METHOD in supported
    assert ChunkType.INTERFACE not in supported


def test_parse_result_structure():
    """Test that parse results have the correct structure."""
    parser = MockParser()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test(): pass")
        f.flush()
        
        try:
            result = parser.parse_file(Path(f.name))
            
            # Check result structure
            assert hasattr(result, 'chunks')
            assert hasattr(result, 'language')
            assert hasattr(result, 'total_chunks')
            assert hasattr(result, 'parse_time')
            assert hasattr(result, 'errors')
            assert hasattr(result, 'warnings')
            assert hasattr(result, 'metadata')
            
            assert result.language == Language.PYTHON
            assert isinstance(result.parse_time, float)
            assert isinstance(result.errors, list)
            assert isinstance(result.warnings, list)
            assert isinstance(result.metadata, dict)
            
        finally:
            Path(f.name).unlink()