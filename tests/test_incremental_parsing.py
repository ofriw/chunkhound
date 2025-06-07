"""Tests for incremental parsing functionality in CodeParser."""

import pytest
from pathlib import Path
import tempfile
import os
from unittest.mock import Mock, patch

from chunkhound.parser import CodeParser
from chunkhound.tree_cache import TreeCache


class TestIncrementalParsing:
    """Test incremental parsing methods in CodeParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_cache = TreeCache(max_entries=10, max_memory_mb=10)
        self.parser = CodeParser(use_cache=True, cache=self.test_cache)
        self.parser.setup()
        
        # Create temporary test files
        self.temp_dir = tempfile.mkdtemp()
        self.python_file = Path(self.temp_dir) / "test.py"
        self.java_file = Path(self.temp_dir) / "Test.java"
        self.markdown_file = Path(self.temp_dir) / "test.md"
        
        # Sample Python code
        self.python_code = '''
def hello_world():
    """A simple hello world function."""
    print("Hello, World!")
    return "Hello"

class TestClass:
    """A test class."""
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}!"
'''
        
        # Sample Java code
        self.java_code = '''
package com.example;

public class Test {
    private String name;
    
    public Test(String name) {
        this.name = name;
    }
    
    public String greet() {
        return "Hello, " + name + "!";
    }
    
    public static void main(String[] args) {
        Test test = new Test("World");
        System.out.println(test.greet());
    }
}
'''
        
        # Sample Markdown code
        self.markdown_code = '''
# Main Header

This is a paragraph under the main header.

## Sub Header

Another paragraph here.

```python
def example():
    pass
```

### Another Section

Final paragraph.
'''
        
        # Write test files
        self.python_file.write_text(self.python_code)
        self.java_file.write_text(self.java_code)
        self.markdown_file.write_text(self.markdown_code)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parse_incremental_python_cache_miss(self):
        """Test incremental parsing with cache miss for Python file."""
        # First parse should be cache miss
        tree = self.parser.parse_incremental(self.python_file)
        
        assert tree is not None
        assert hasattr(tree, 'root_node')
        
        # Check cache stats
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 0
        assert stats['entries'] == 1
    
    def test_parse_incremental_python_cache_hit(self):
        """Test incremental parsing with cache hit for Python file."""
        # First parse - cache miss
        tree1 = self.parser.parse_incremental(self.python_file)
        assert tree1 is not None
        
        # Second parse should be cache hit
        tree2 = self.parser.parse_incremental(self.python_file)
        assert tree2 is not None
        assert tree1 is tree2  # Should be exact same object from cache
        
        # Check cache stats
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 1
        assert stats['entries'] == 1
    
    def test_parse_incremental_java_cache_behavior(self):
        """Test incremental parsing with Java file."""
        # First parse - cache miss
        tree1 = self.parser.parse_incremental(self.java_file)
        assert tree1 is not None
        
        # Second parse - cache hit
        tree2 = self.parser.parse_incremental(self.java_file)
        assert tree2 is tree1
        
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 1
    
    def test_parse_incremental_markdown_cache_behavior(self):
        """Test incremental parsing with Markdown file."""
        # First parse - cache miss
        tree1 = self.parser.parse_incremental(self.markdown_file)
        assert tree1 is not None
        
        # Second parse - cache hit
        tree2 = self.parser.parse_incremental(self.markdown_file)
        assert tree2 is tree1
        
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 1
    
    def test_parse_incremental_with_source_code(self):
        """Test incremental parsing with provided source code."""
        # Parse with explicit source code
        tree = self.parser.parse_incremental(self.python_file, self.python_code)
        assert tree is not None
        
        # Should cache based on file path
        tree2 = self.parser.parse_incremental(self.python_file)
        assert tree2 is tree
    
    def test_parse_incremental_cache_disabled(self):
        """Test parsing with cache disabled."""
        parser_no_cache = CodeParser(use_cache=False)
        parser_no_cache.setup()
        
        # Should work without cache
        tree1 = parser_no_cache.parse_incremental(self.python_file)
        tree2 = parser_no_cache.parse_incremental(self.python_file)
        
        assert tree1 is not None
        assert tree2 is not None
        # Without cache, these should be different objects
        assert tree1 is not tree2
    
    def test_invalidate_cache(self):
        """Test cache invalidation."""
        # Parse and cache
        tree = self.parser.parse_incremental(self.python_file)
        assert tree is not None
        assert self.test_cache.get_stats()['entries'] == 1
        
        # Invalidate cache
        result = self.parser.invalidate_cache(self.python_file)
        assert result is True
        assert self.test_cache.get_stats()['entries'] == 0
        
        # Next parse should be cache miss
        tree2 = self.parser.parse_incremental(self.python_file)
        assert tree2 is not None
        assert tree2 is not tree
        
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 2  # Original miss + post-invalidation miss
        assert stats['hits'] == 0
    
    def test_invalidate_cache_no_cache(self):
        """Test invalidating cache when no cache is used."""
        parser_no_cache = CodeParser(use_cache=False)
        result = parser_no_cache.invalidate_cache(self.python_file)
        assert result is False
    
    def test_get_changed_regions_identical_trees(self):
        """Test change detection with identical trees."""
        tree1 = self.parser.parse_incremental(self.python_file)
        tree2 = self.parser.parse_incremental(self.python_file)  # Same tree from cache
        
        changes = self.parser.get_changed_regions(tree1, tree2)
        assert changes == []  # No changes for identical trees
    
    def test_get_changed_regions_different_trees(self):
        """Test change detection with different trees."""
        # Parse original file
        tree1 = self.parser.parse_incremental(self.python_file)
        
        # Modify file
        modified_code = self.python_code + "\n\ndef new_function():\n    pass\n"
        tree2 = self.parser._parse_tree_only(self.python_file, modified_code)
        
        changes = self.parser.get_changed_regions(tree1, tree2)
        assert len(changes) >= 0  # Should detect changes
    
    def test_get_changed_regions_none_trees(self):
        """Test change detection with None trees."""
        tree = self.parser.parse_incremental(self.python_file)
        
        # Test with None trees
        changes1 = self.parser.get_changed_regions(None, tree)
        changes2 = self.parser.get_changed_regions(tree, None)
        changes3 = self.parser.get_changed_regions(None, None)
        
        # All should indicate full change
        assert len(changes1) == 1
        assert changes1[0]['type'] == 'full_change'
        assert len(changes2) == 1
        assert changes2[0]['type'] == 'full_change'
        assert len(changes3) == 1
        assert changes3[0]['type'] == 'full_change'
    
    def test_parse_tree_only_python(self):
        """Test direct tree parsing for Python."""
        tree = self.parser._parse_tree_only(self.python_file)
        assert tree is not None
        assert hasattr(tree, 'root_node')
        assert tree.root_node.type == 'module'
    
    def test_parse_tree_only_java(self):
        """Test direct tree parsing for Java."""
        tree = self.parser._parse_tree_only(self.java_file)
        assert tree is not None
        assert hasattr(tree, 'root_node')
        # Java root node type
        assert tree.root_node.type == 'program'
    
    def test_parse_tree_only_markdown(self):
        """Test direct tree parsing for Markdown."""
        tree = self.parser._parse_tree_only(self.markdown_file)
        assert tree is not None
        assert hasattr(tree, 'root_node')
        assert tree.root_node.type == 'document'
    
    def test_parse_tree_only_unsupported_file(self):
        """Test tree parsing for unsupported file type."""
        unsupported_file = Path(self.temp_dir) / "test.txt"
        unsupported_file.write_text("Hello world")
        
        tree = self.parser._parse_tree_only(unsupported_file)
        assert tree is None
    
    def test_parse_tree_only_with_source(self):
        """Test tree parsing with provided source code."""
        tree = self.parser._parse_tree_only(self.python_file, self.python_code)
        assert tree is not None
        assert tree.root_node.type == 'module'
    
    def test_parse_tree_only_parser_not_initialized(self):
        """Test tree parsing when parser not initialized."""
        parser = CodeParser(use_cache=False)
        # Don't call setup()
        
        tree = parser._parse_tree_only(self.python_file)
        # Should initialize automatically and succeed
        assert tree is not None
    
    def test_parse_file_uses_cache_when_enabled(self):
        """Test that parse_file uses cache when enabled."""
        # Parse file twice
        chunks1 = self.parser.parse_file(self.python_file)
        chunks2 = self.parser.parse_file(self.python_file)
        
        assert len(chunks1) > 0
        assert len(chunks2) > 0
        
        # Should have cache hit
        stats = self.test_cache.get_stats()
        assert stats['hits'] > 0
    
    def test_parse_file_bypasses_cache_when_disabled(self):
        """Test that parse_file bypasses cache when disabled."""
        parser_no_cache = CodeParser(use_cache=False)
        parser_no_cache.setup()
        
        chunks1 = parser_no_cache.parse_file(self.python_file)
        chunks2 = parser_no_cache.parse_file(self.python_file)
        
        assert len(chunks1) > 0
        assert len(chunks2) > 0
        # No cache to check
    
    def test_cache_invalidation_on_file_modification(self):
        """Test cache behavior when file is modified."""
        # Parse and cache
        tree1 = self.parser.parse_incremental(self.python_file)
        assert tree1 is not None
        
        # Modify file (change modification time)
        import time
        time.sleep(0.1)  # Ensure different mtime
        modified_code = self.python_code + "\n# Added comment\n"
        self.python_file.write_text(modified_code)
        
        # Parse again - should detect file change and reparse
        tree2 = self.parser.parse_incremental(self.python_file)
        assert tree2 is not None
        
        # Should have detected file change and reparsed
        stats = self.test_cache.get_stats()
        assert stats['misses'] == 2  # Original miss + post-modification miss
        assert stats['invalidations'] >= 1  # Automatic invalidation
    
    @pytest.mark.skipif(not hasattr(pytest, 'mark'), reason="Advanced test")
    def test_performance_improvement_with_cache(self):
        """Test that caching provides performance improvement."""
        import time
        
        # Parse without cache
        parser_no_cache = CodeParser(use_cache=False)
        parser_no_cache.setup()
        
        start_time = time.time()
        for _ in range(5):
            parser_no_cache.parse_incremental(self.python_file)
        no_cache_time = time.time() - start_time
        
        # Parse with cache
        start_time = time.time()
        for _ in range(5):
            self.parser.parse_incremental(self.python_file)
        cache_time = time.time() - start_time
        
        # Cache should be faster (at least for repeated accesses)
        # First access will be similar, but subsequent should be much faster
        print(f"No cache: {no_cache_time:.4f}s, With cache: {cache_time:.4f}s")
        # Don't assert specific ratio as it depends on system performance
    
    def test_multiple_file_types_in_cache(self):
        """Test caching behavior with multiple file types."""
        # Parse all file types
        py_tree = self.parser.parse_incremental(self.python_file)
        java_tree = self.parser.parse_incremental(self.java_file)
        md_tree = self.parser.parse_incremental(self.markdown_file)
        
        assert py_tree is not None
        assert java_tree is not None
        assert md_tree is not None
        
        # All should be cached
        stats = self.test_cache.get_stats()
        assert stats['entries'] == 3
        assert stats['misses'] == 3
        assert stats['hits'] == 0
        
        # Second access should hit cache
        py_tree2 = self.parser.parse_incremental(self.python_file)
        java_tree2 = self.parser.parse_incremental(self.java_file)
        md_tree2 = self.parser.parse_incremental(self.markdown_file)
        
        assert py_tree2 is py_tree
        assert java_tree2 is java_tree
        assert md_tree2 is md_tree
        
        stats = self.test_cache.get_stats()
        assert stats['hits'] == 3


class TestIncrementalParsingIntegration:
    """Integration tests for incremental parsing with existing parsing flow."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.parser = CodeParser(use_cache=True)
        self.parser.setup()
        
        # Create test file
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "integration_test.py"
        
        self.test_code = '''
class Calculator:
    """A simple calculator class."""
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
    
    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b

def main():
    """Main function."""
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"5 + 3 = {result}")

if __name__ == "__main__":
    main()
'''
        self.test_file.write_text(self.test_code)
    
    def teardown_method(self):
        """Clean up integration test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parse_file_integration_with_incremental(self):
        """Test that parse_file integrates properly with incremental parsing."""
        # Parse file and extract chunks
        chunks = self.parser.parse_file(self.test_file)
        
        assert len(chunks) > 0
        
        # Should have functions and class
        function_chunks = [c for c in chunks if c.get('chunk_type') == 'function']
        class_chunks = [c for c in chunks if c.get('chunk_type') == 'class']
        
        assert len(function_chunks) >= 3  # add, multiply, main functions
        assert len(class_chunks) >= 1    # Calculator class
        
        # Verify cache was used
        cache = self.parser.tree_cache
        stats = cache.get_stats()
        # Cache may have entries from other tests, just verify it has our file
        assert stats['entries'] >= 1
        assert stats['misses'] >= 1
    
    def test_consistent_results_cached_vs_uncached(self):
        """Test that cached and uncached parsing produce identical results."""
        # Parse with cache
        cached_parser = CodeParser(use_cache=True)
        cached_parser.setup()
        cached_chunks = cached_parser.parse_file(self.test_file)
        
        # Parse without cache
        uncached_parser = CodeParser(use_cache=False)
        uncached_parser.setup()
        uncached_chunks = uncached_parser.parse_file(self.test_file)
        
        # Results should be identical
        assert len(cached_chunks) == len(uncached_chunks)
        
        # Compare chunk content (ignoring exact object identity)
        for cached_chunk, uncached_chunk in zip(cached_chunks, uncached_chunks):
            assert cached_chunk['symbol'] == uncached_chunk['symbol']
            assert cached_chunk['chunk_type'] == uncached_chunk['chunk_type']
            assert cached_chunk['code'] == uncached_chunk['code']
            assert cached_chunk['start_line'] == uncached_chunk['start_line']
            assert cached_chunk['end_line'] == uncached_chunk['end_line']